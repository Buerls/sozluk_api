# api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views # views.py dosyamızdaki view'ları import ediyoruz

# DefaultRouter'ı başlatıyoruz
router = DefaultRouter()

# ViewSet'lerimizi router'a kaydediyoruz.
# router.register(r'url_prefix', ViewSetClass, basename='opsiyonel_base_name')
router.register(r'users', views.UserViewSet)
router.register(r'profiles', views.ProfileViewSet)
router.register(r'topics', views.TopicViewSet,basename='topic')
router.register(r'entries', views.EntryViewSet)
router.register(r'votes', views.VoteViewSet)
router.register(r'favorites', views.FavoriteViewSet)
router.register(r'topic-follows', views.TopicFollowViewSet) # URL prefix'i '-' ile ayırmak yaygındır
router.register(r'user-follows', views.UserFollowViewSet)

# URLConf'umuz. Router tarafından otomatik oluşturulan URL'leri içerir.
urlpatterns = [
    path('', include(router.urls)),
    path('register/', views.RegistrationView.as_view(), name='register'),
    # Gelecekte buraya router dışı özel URL'ler de ekleyebiliriz (örn: login/register için).
]