# api/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User # Veya settings.AUTH_USER_MODEL
from .models import Profile, Topic, Entry, Vote, Favorite, TopicFollow, UserFollow

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password # Django'nun şifre doğrulama araçları
from rest_framework import serializers
# from django.conf import settings # Eğer AUTH_USER_MODEL kullanıyorsanız

# AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')

# Kullanıcı bilgilerini göstermek için basit bir serializer
# (Şifre gibi hassas bilgileri içermez)
class UserSerializer(serializers.ModelSerializer):
    # Profil bilgilerini de eklemek istersek (read_only çünkü User üzerinden Profile update etmeyiz genelde)
    # profile = ProfileSerializer(read_only=True) # ProfileSerializer'ın bu satırdan ÖNCE tanımlanması gerekir
    class Meta:
        # model = AUTH_USER_MODEL # Eğer settings'den alıyorsanız
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name'] # Göstermek istediğimiz alanlar
        # 'profile' alanını eklemek için fields'a ekleyin

class ProfileSerializer(serializers.ModelSerializer):
    # User alanını sadece okunabilir ve username olarak göstermek için:
    # user = serializers.ReadOnlyField(source='user.username')
    # Veya User'ın ID'sini göstermek için varsayılan haliyle bırakabiliriz.
    # Veya tam User objesini iç içe göstermek için:
    user = UserSerializer(read_only=True) # Profile update ederken user'ı değiştirmeyiz

    class Meta:
        model = Profile
        fields = ['id', 'user', 'bio', 'avatar', 'location', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class TopicSerializer(serializers.ModelSerializer):
    # Yazarın sadece ID'si yerine username'ini göstermek için ReadOnlyField kullanabiliriz.
    author_username = serializers.ReadOnlyField(source='author.username')
    # Veya iç içe UserSerializer kullanabiliriz:
    # author = UserSerializer(read_only=True)
    first_entry_content_display = serializers.CharField(source='first_entry_content', read_only=True, allow_null=True) # Okuma için önceki adımdaki alan (ismi değiştirdim)

    first_entry_content_input = serializers.CharField(
        write_only=True,  # Sadece yazma işlemi için (API yanıtında görünmez)
        required=True,  # Bu alanın gönderilmesi zorunlu
        allow_blank=False,  # Boş gönderilemez
        style={'base_template': 'textarea.html'}  # DRF Browsable API'de textarea olarak görünür
    )

    class Meta:
        model = Topic
        fields = [
            'id',
            'title', # title create sırasında gönderilecek
            'author',
            'author_username',
            'created_at',
            'first_entry_content_display', # Okuma için
            'first_entry_content_input', # Yazma için
        ]

        read_only_fields = ['author', 'created_at', 'author_username', 'first_entry_content_display']


class EntrySerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source='author.username')
    # topic_title = serializers.ReadOnlyField(source='topic.title') # Başlık ismini de ekleyelim

    # Oy sayılarını göstermek için (Eğer modelde tutmuyorsak, hesaplamamız gerekir)
    # votes_count = serializers.SerializerMethodField() # Hesaplanan alan örneği
    # upvotes = serializers.SerializerMethodField()
    # downvotes = serializers.SerializerMethodField()

    upvotes_count = serializers.SerializerMethodField(read_only=True)
    downvotes_count = serializers.SerializerMethodField(read_only=True)
    current_user_vote = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Entry
        fields = [
            'id',
            'topic', # Sadece topic ID'si
            # 'topic_title', # Eğer gösterilecekse
            'author', # Author ID'si
            'author_username',
            'content',
            'created_at',
            'updated_at',
            # Yeni alanları fields listesine ekle:
            'upvotes_count',
            'downvotes_count',
            'current_user_vote',
        ]
        # read_only_fields listesine eklemeye gerek yok, SerializerMethodField zaten read-only.
        # read_only_fields = ['author', 'created_at', 'updated_at', 'author_username'] # topic_title da olabilir

    # Örnek: Oy sayılarını hesaplayan metodlar (performans için optimize edilmeli)
    # def get_votes_count(self, obj):
    #     return obj.votes.count() # İlişkili tüm oylar
    # def get_upvotes(self, obj):
    #     return obj.votes.filter(vote_type=Vote.UPVOTE).count()
    # def get_downvotes(self, obj):
    #     return obj.votes.filter(vote_type=Vote.DOWNVOTE).count()

    def get_upvotes_count(self, obj: Entry):
        """ İlgili entry için upvote sayısını döndürür. """
        # obj -> mevcut Entry instance'ı
        # obj.votes -> Entry modelindeki Vote ilişkisi (related_name='votes' varsayımıyla)
        return obj.votes.filter(vote_type=Vote.UPVOTE).count()


    def get_downvotes_count(self, obj: Entry):
        """ İlgili entry için downvote sayısını döndürür. """
        return obj.votes.filter(vote_type=Vote.DOWNVOTE).count()

    def get_current_user_vote(self, obj: Entry):
        """
        İsteği yapan kullanıcının bu entry'ye verdiği oyu döndürür (+1, -1 veya None).
        Serializer context'inde 'request' nesnesinin bulunmasını gerektirir.
        """
        request = self.context.get('request', None)
        if request is None or not request.user.is_authenticated:
            return None # Kullanıcı giriş yapmamışsa veya request context'i yoksa

        # Kullanıcının bu entry ('obj') için verdiği oyu bulmaya çalış
        vote = Vote.objects.filter(entry=obj, user=request.user).first() # obj.votes yerine doğrudan Vote modelini kullandık
        if vote:
            return vote.vote_type # Oy varsa, oy tipini (+1 veya -1) döndür
        return None # Kullanıcının oyu yoksa None döndür


class VoteSerializer(serializers.ModelSerializer):
    # Oy veren kullanıcının username'ini ekleyelim (sadece okuma)
    user_username = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Vote
        fields = ['id', 'user', 'user_username', 'entry', 'vote_type', 'created_at']
        # user ve created_at genelde otomatik atanır
        read_only_fields = ['user', 'created_at', 'user_username']


class FavoriteSerializer(serializers.ModelSerializer):
    user_username = serializers.ReadOnlyField(source='user.username')
    # Favorilenen entry hakkında kısa bilgi (örn: entry ID ve başlığı)
    entry_info = serializers.ReadOnlyField(source='entry.__str__') # Entry'nin __str__ metodunu kullanır

    class Meta:
        model = Favorite
        fields = ['id', 'user', 'user_username', 'entry', 'entry_info', 'created_at']
        read_only_fields = ['user', 'created_at', 'user_username', 'entry_info']


class TopicFollowSerializer(serializers.ModelSerializer):
    user_username = serializers.ReadOnlyField(source='user.username')
    topic_title = serializers.ReadOnlyField(source='topic.title')

    class Meta:
        model = TopicFollow
        fields = ['id', 'user', 'user_username', 'topic', 'topic_title', 'created_at']
        read_only_fields = ['user', 'created_at', 'user_username', 'topic_title']


class UserFollowSerializer(serializers.ModelSerializer):
    follower_username = serializers.ReadOnlyField(source='follower.username')
    followed_username = serializers.ReadOnlyField(source='followed.username')

    class Meta:
        model = UserFollow
        fields = ['id', 'follower', 'follower_username', 'followed', 'followed_username', 'created_at']
        read_only_fields = ['follower', 'created_at', 'follower_username', 'followed_username']

class UserRegistrationSerializer(serializers.ModelSerializer):
    # Şifre tekrarı için ekstra alan ekliyoruz
    password2 = serializers.CharField(style={'input_type': 'password'}, write_only=True, label="Password Confirmation")

    class Meta:
        model = User
        # Kayıt sırasında almak istediğimiz alanlar
        fields = ['username', 'email', 'password', 'password2', 'first_name', 'last_name']
        extra_kwargs = {
            'password': {'write_only': True, # Şifreyi API yanıtında göstermemek için
                         'validators': [validate_password]}, # Django'nun güçlü şifre politikalarını uygula
            'email': {'required': True}, # E-postayı zorunlu yapalım
            'first_name': {'required': False}, # İsim soyisim opsiyonel olabilir
            'last_name': {'required': False},
        }

    def validate(self, attrs):
        """ Şifrelerin eşleşip eşleşmediğini kontrol et """
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        # Diğer özel doğrulamalar buraya eklenebilir
        return attrs

    def create(self, validated_data):
        """ Kullanıcıyı oluştur """
        # password2'yi validated_data'dan çıkarıyoruz, User modelinde böyle bir alan yok
        validated_data.pop('password2')
        # create_user metodu şifreyi otomatik olarak hash'ler
        user = User.objects.create_user(**validated_data)

        # İsterseniz burada kullanıcıya ait bir Profile nesnesi de oluşturabilirsiniz
        # Profile.objects.create(user=user)

        return user