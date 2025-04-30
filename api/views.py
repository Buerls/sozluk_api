# api/views.py
from django.contrib.auth.models import User # Veya settings.AUTH_USER_MODEL
from django.db import transaction
from django.db.models import OuterRef, Subquery
from rest_framework import viewsets, permissions, generics, status, serializers, filters
from rest_framework.decorators import action
from rest_framework.response import Response
# from django.shortcuts import get_object_or_404 # Gerekirse
from .permissions import IsOwnerOrReadOnly # Yeni izni import et


from .models import Profile, Topic, Entry, Vote, Favorite, TopicFollow, UserFollow
from .serializers import (
    UserSerializer, ProfileSerializer, TopicSerializer, EntrySerializer,
    VoteSerializer, FavoriteSerializer, TopicFollowSerializer, UserFollowSerializer, UserRegistrationSerializer
)

# Kendi izinlerimizi yazmak için (örneğin sadece objenin sahibi düzenleyebilsin)
# from .permissions import IsOwnerOrReadOnly # Bu dosyayı oluşturmamız gerekir

# --- ViewSet Tanımları ---

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Kullanıcıları listelemek ve detaylarını görmek için API endpoint'i.
    ReadOnly: Sadece okuma işlemleri (list, retrieve).
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    # Tüm kullanıcıları herkes görebilir mi, yoksa sadece giriş yapanlar mı?
    permission_classes = [permissions.IsAuthenticated,IsOwnerOrReadOnly] # Veya AllowAny? Projeye göre karar verilir.



class ProfileViewSet(viewsets.ModelViewSet):
    """
    Profilleri listelemek, oluşturmak, güncellemek, silmek için API endpoint'i.
    """
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    # Sadece profil sahibi kendi profilini güncelleyebilmeli/silebilmeli.
    # Herkes profilleri okuyabilmeli.
    # permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly] # Özel permission lazım
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly] # Şimdilik basit tutalım

    # Profil oluşturulurken user otomatik olarak request.user atanmalı
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class TopicViewSet(viewsets.ModelViewSet):
    # queryset = Topic.objects.all().order_by('-created_at') # Bu satırı kaldır veya yorumla
    serializer_class = TopicSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'author__username']

    # get_queryset metodunu override ediyoruz
    def get_queryset(self):
        """
        Her başlığa ilişkili ilk entry'nin içeriğini ekler (annotate eder).
        """
        # İlk entry'nin içeriğini almak için bir alt sorgu (subquery) tanımla:
        # OuterRef('pk') -> Ana sorgudaki (Topic) her bir satırın primary key'ine referans verir.
        # filter(topic=OuterRef('pk')) -> Entry'leri ana sorgudaki Topic'e göre filtreler.
        # order_by('created_at') -> Entry'leri oluşturulma tarihine göre sıralar (en eski başta).
        # values('content')[:1] -> Sıralanmış entry'lerden ilkinin sadece 'content' alanını alır.
        first_entry_content_subquery = Entry.objects.filter(
            topic=OuterRef('pk')
        ).order_by('created_at').values('content')[:1]

        # Ana Topic sorgusunu yap ve subquery sonucunu 'first_entry_content' olarak ekle
        queryset = Topic.objects.annotate(
            first_entry_content=Subquery(first_entry_content_subquery)
        ).order_by('-created_at')  # Sıralamayı burada yapabiliriz

        return queryset

    def perform_create(self, serializer):
        # validated_data'dan entry içeriğini al (serializer'dan gelecek)
        entry_content = serializer.validated_data.pop('first_entry_content_input')

        try:
            # İki veritabanı işlemini atomik yap (biri başarısız olursa diğeri geri alınır)
            with transaction.atomic():
                # Önce Topic'i kaydet (author otomatik atanır)
                topic_instance = serializer.save(author=self.request.user)

                # Sonra ilk Entry'yi oluştur
                Entry.objects.create(
                    topic=topic_instance,
                    author=self.request.user,
                    content=entry_content
                )
                print(f"Topic '{topic_instance.title}' and its first entry created successfully.")
        except Exception as e:
            # Eğer bir hata olursa logla ve DRF'in hata vermesini sağla
            # (Normalde atomic transaction hatayı otomatik yönetir ama loglamak iyi olabilir)
            print(f"Error during atomic creation of topic and first entry: {e}")
            # DRF'in hatayı handle etmesi için tekrar raise edebiliriz veya Validation Error fırlatabiliriz
            raise serializers.ValidationError("Could not create topic and initial entry.") # Örnek


# api/views.py

class EntryViewSet(viewsets.ModelViewSet):
    # ... (serializer_class, permission_classes vb.) ...
    serializer_class = EntrySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    queryset = Entry.objects.all().order_by('created_at') # Temel queryset

    @action(detail=True, methods=['post', 'delete'], permission_classes=[permissions.IsAuthenticated])
    def vote(self, request, pk=None):
        """
        Bir entry için oy verme (POST) veya oyu silme (DELETE) işlemi.
        POST isteği body'sinde {'vote_type': 1} veya {'vote_type': -1} beklenir.
        """
        entry = self.get_object()  # URL'deki pk ile ilgili Entry'i al
        user = request.user

        if request.method == 'POST':
            vote_type_str = request.data.get('vote_type')
            try:
                vote_type = int(vote_type_str)
                if vote_type not in [Vote.UPVOTE, Vote.DOWNVOTE]:  # Sadece 1 veya -1 kabul et
                    raise ValueError('Invalid vote type value.')
            except (ValueError, TypeError):
                return Response(
                    {'detail': 'Invalid or missing vote_type. Use 1 for upvote, -1 for downvote.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Mevcut oyu bul veya yoksa oluştur/güncelle
            # defaults -> Eğer yeni kayıt oluşturulmuyorsa güncellenecek alanlar
            vote, created = Vote.objects.update_or_create(
                entry=entry, user=user,
                defaults={'vote_type': vote_type}
            )

            status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
            # Başarı yanıtı olarak güncellenmiş entry'i veya basit bir mesajı dönebiliriz.
            # Şimdilik basit mesaj dönelim:
            return Response({'status': 'vote set', 'vote_type': vote.vote_type}, status=status_code)

        elif request.method == 'DELETE':
            # Kullanıcının bu entry için oyunu sil
            deleted_count, _ = Vote.objects.filter(entry=entry, user=user).delete()

            if deleted_count > 0:
                # Başarıyla silindi, içerik yok yanıtı dön
                return Response(status=status.HTTP_204_NO_CONTENT)
            else:
                # Kullanıcının zaten oyu yoksa hata dön
                return Response({'detail': 'You had not voted on this entry.'}, status=status.HTTP_404_NOT_FOUND)

    def get_queryset(self):
        """
        Optionally restricts the returned entries to a given topic,
        by filtering against a `topic` query parameter in the URL.
        """
        queryset = super().get_queryset() # veya Entry.objects.all()
        topic_id = self.request.query_params.get('topic')
        if topic_id is not None:
            try:
                # Gelen topic_id geçerli bir sayı mı ve var olan bir başlığa mı ait?
                topic_id = int(topic_id)
                queryset = queryset.filter(topic_id=topic_id)
            except (ValueError, Topic.DoesNotExist):
                # Geçersiz topic_id durumunda boş queryset döndürebilir veya hata verebiliriz.
                # Şimdilik boş döndürelim.
                queryset = queryset.none() # Veya hata fırlat: raise Http404
        return queryset

    def perform_create(self, serializer):
        # Entry oluştururken 'topic' alanını nasıl atayacağız?
        # Ya request datasından gelmeli ya da URL'den (nested routing).
        # Query parametresi ile filtreleme yapıyorsak, topic'in request datasında
        # gönderilmesi beklenebilir veya view'da manuel olarak ayarlanabilir.
        # Şimdilik serializer'ın topic'i handle ettiğini varsayalım (request data).
        # Eğer topic'i request data'da zorunlu kılmak istemiyorsak,
        # view'da bu kontrolü yapmalıyız.
        topic_id = serializer.validated_data.get('topic', None)
        if topic_id is None and 'topic' in self.request.data:
             # Belki de request.data'dan almaya çalışabiliriz (serializer'da yoksa)
             # VEYA hata fırlatabiliriz: raise serializers.ValidationError("Topic is required.")
             pass # Şimdilik geçelim, serializer'ın hallettiğini varsayıyoruz.

        serializer.save(author=self.request.user)
        # ÖNEMLİ NOT: Eğer topic zorunlu ise ve serializer'dan gelmiyorsa,
        # perform_create içinde topic_id'yi alıp serializer.save içine eklemeniz gerekir.
        # Örn: topic = get_object_or_404(Topic, pk=self.request.data.get('topic'))
        #      serializer.save(author=self.request.user, topic=topic)

class VoteViewSet(viewsets.ModelViewSet):
    """
    Oyları listelemek (belki?), oy oluşturmak, silmek (oy geri alma) için endpoint.
    Genellikle sadece create ve destroy kullanılır. Update pek mantıklı değil.
    """
    queryset = Vote.objects.all()
    serializer_class = VoteSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    # Oyu atan kullanıcıyı otomatik olarak request.user yap
    def perform_create(self, serializer):
        # Aynı entry'e tekrar oy vermeyi engelle (unique_together modelde var ama burada da kontrol iyi olabilir)
        entry = serializer.validated_data['entry']
        existing_vote = Vote.objects.filter(user=self.request.user, entry=entry).first()
        if existing_vote:
            # Eğer aynı türde oy veriyorsa hata ver veya görmezden gel
            # Eğer farklı türde oy veriyorsa eskisini silip yenisini ekle veya güncelle (proje kararı)
            # Şimdilik basitçe hata verelim veya mevcut oyu güncelleyelim
            if existing_vote.vote_type == serializer.validated_data['vote_type']:
                 # Belki mevcut oyu silip işlemi iptal etmeli? Veya hata vermeli.
                 raise serializers.ValidationError({"detail": "You have already voted this way."})
            else:
                existing_vote.vote_type = serializer.validated_data['vote_type']
                existing_vote.save()
                # serializer.instance = existing_vote # Güncellenen örneği döndürmek için
                # return Response(serializer.data, status=status.HTTP_200_OK) # Direkt güncellenmiş veri dönebiliriz
                # Ya da raise ValidationError
        else:
            serializer.save(user=self.request.user)


class FavoriteViewSet(viewsets.ModelViewSet):
    """ Favorileri listelemek, favori eklemek, silmek için endpoint. """
    queryset = Favorite.objects.all()
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    # Sadece giriş yapan kullanıcının kendi favorilerini listelemesi için:
    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user)

    # Favori eklerken kullanıcıyı otomatik ata
    def perform_create(self, serializer):
         # Tekrar favorilemeyi engelle (unique_together modelde var ama...)
        entry = serializer.validated_data['entry']
        if Favorite.objects.filter(user=self.request.user, entry=entry).exists():
            raise serializers.ValidationError({"detail": "You have already favorited this entry."})
        serializer.save(user=self.request.user)


class TopicFollowViewSet(viewsets.ModelViewSet):
    """ Takip edilen başlıkları listele, takip et, takibi bırak endpoint'i. """
    queryset = TopicFollow.objects.all().order_by('-created_at')
    serializer_class = TopicSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    # Arama ve Filtreleme backend'lerini ekliyoruz
    filter_backends = [filters.SearchFilter]  # İleride OrderingFilter, DjangoFilterBackend eklenebilir
    search_fields = ['title', 'author__username']  # Hangi alanlarda arama yapılacağı
    # '=' -> Tam eşleşme
    # '^' -> Başlangıç eşleşmesi
    # '@' -> Full-text search (destekleyen DB'lerde)
    # '$' -> Regex search
    # Varsayılan: icontains (case-insensitive partial match)



    def get_queryset(self):
        return TopicFollow.objects.filter(user=self.request.user) # Sadece kullanıcının takip ettikleri

    def perform_create(self, serializer):
        topic = serializer.validated_data['topic']
        if TopicFollow.objects.filter(user=self.request.user, topic=topic).exists():
             raise serializers.ValidationError({"detail": "You are already following this topic."})
        serializer.save(user=self.request.user)


class UserFollowViewSet(viewsets.ModelViewSet):
    """ Takip edilen/eden kullanıcıları listele, takip et, takibi bırak endpoint'i. """
    queryset = UserFollow.objects.all()
    serializer_class = UserFollowSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    # Kullanıcının takip ettiklerini veya takipçilerini listelemek için filtreleme gerekebilir
    # def get_queryset(self):
    #     user = self.request.user
    #     filter_type = self.request.query_params.get('type', 'following') # following or followers
    #     if filter_type == 'followers':
    #         return UserFollow.objects.filter(followed=user)
    #     else: # Default to following
    #         return UserFollow.objects.filter(follower=user)

    def perform_create(self, serializer):
        followed_user = serializer.validated_data['followed']
        if self.request.user == followed_user:
            raise serializers.ValidationError({"detail": "You cannot follow yourself."})
        if UserFollow.objects.filter(follower=self.request.user, followed=followed_user).exists():
            raise serializers.ValidationError({"detail": "You are already following this user."})
        serializer.save(follower=self.request.user)


class RegistrationView(generics.CreateAPIView):
    """
    Yeni kullanıcı kaydı için endpoint.
    """
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny] # Herkesin kaydolabilmesi için izin veriyoruz