from django.contrib import admin
from .models import Profile, Topic, Entry, Vote, Favorite, TopicFollow, UserFollow
# Register your models here.
admin.site.register(Profile)
admin.site.register(Topic)
admin.site.register(Entry)
admin.site.register(Vote)
admin.site.register(Favorite)
admin.site.register(TopicFollow)
admin.site.register(UserFollow)