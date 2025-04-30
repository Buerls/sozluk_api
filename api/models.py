# api/models.py
from django.db import models
from django.contrib.auth.models import User # Veya settings.AUTH_USER_MODEL
from django.conf import settings

# Use AUTH_USER_MODEL for better flexibility if you might customize the user model later
AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')

class Profile(models.Model):
    """ Model to store additional user information (bio, avatar, etc.) """
    user = models.OneToOneField(AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile', verbose_name="User")
    bio = models.TextField(blank=True, null=True, verbose_name="Biography")
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Avatar") # Requires Pillow
    location = models.CharField(max_length=100, blank=True, null=True, verbose_name="Location")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    def __str__(self):
        return f"{self.user.username}'s Profile"

    class Meta:
        verbose_name = "Profile"
        verbose_name_plural = "Profiles"

class Topic(models.Model):
    """ Model representing topics (headings) """
    title = models.CharField(max_length=200, unique=True, db_index=True, verbose_name="Title")
    # Use AUTH_USER_MODEL for the foreign key
    author = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='topics', verbose_name="Author")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Created At")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Topic"
        verbose_name_plural = "Topics"
        ordering = ['-created_at'] # Default ordering (newest first)

class Entry(models.Model):
    """ Model representing entries written under topics """
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='entries', verbose_name="Topic")
    # Use AUTH_USER_MODEL for the foreign key
    author = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='entries', verbose_name="Author") # Changed related_name for clarity if User has other 'entries'
    content = models.TextField(verbose_name="Content")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    # Optional denormalized fields for performance:
    # upvotes_count = models.IntegerField(default=0)
    # downvotes_count = models.IntegerField(default=0)

    def __str__(self):
        # Use pk (primary key) which is usually id
        return f"Entry {self.pk} on '{self.topic.title}' by {self.author.username}"

    class Meta:
        verbose_name = "Entry"
        verbose_name_plural = "Entries"
        ordering = ['created_at'] # Default ordering within a topic (oldest first)


class Vote(models.Model):
    """ Model to store votes (upvote/downvote) on entries """
    UPVOTE = 1
    DOWNVOTE = -1
    VOTE_CHOICES = (
        (UPVOTE, 'Upvote'),
        (DOWNVOTE, 'Downvote'),
    )

    # Use AUTH_USER_MODEL for the foreign key
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='votes', verbose_name="User")
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name='votes', verbose_name="Entry")
    vote_type = models.SmallIntegerField(choices=VOTE_CHOICES, verbose_name="Vote Type")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Voted At")

    def __str__(self):
        # Use pk (primary key) which is usually id
        return f"{self.user.username} -> Entry {self.entry.pk} ({self.get_vote_type_display()})"

    class Meta:
        verbose_name = "Vote"
        verbose_name_plural = "Votes"
        # Ensure a user can vote only once per entry
        unique_together = ('user', 'entry')
        ordering = ['-created_at']


class Favorite(models.Model):
    """ Model to store user's favorite entries """
    # Use AUTH_USER_MODEL for the foreign key
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorites', verbose_name="User")
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name='favorited_by', verbose_name="Favorite Entry") # Changed related_name
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Favorited At")

    def __str__(self):
        # Use pk (primary key) which is usually id
        return f"{self.user.username} favorited Entry {self.entry.pk}"

    class Meta:
        verbose_name = "Favorite"
        verbose_name_plural = "Favorites"
        # Ensure a user favorites an entry only once
        unique_together = ('user', 'entry')
        ordering = ['-created_at']


class TopicFollow(models.Model):
    """ Model to store topics followed by users """
    # Use AUTH_USER_MODEL for the foreign key
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='followed_topics', verbose_name="User (Follower)")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='followers', verbose_name="Followed Topic")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Followed At")

    def __str__(self):
        return f"{self.user.username} follows Topic '{self.topic.title}'"

    class Meta:
        verbose_name = "Topic Follow"
        verbose_name_plural = "Topic Follows"
        # Ensure a user follows a topic only once
        unique_together = ('user', 'topic')
        ordering = ['-created_at']


class UserFollow(models.Model):
    """ Model representing the following relationship between users """
    # Use AUTH_USER_MODEL for the foreign keys
    # The user doing the following
    follower = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='following', verbose_name="Follower")
    # The user being followed
    followed = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='followers', verbose_name="Followed")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Followed At")

    def __str__(self):
        return f"{self.follower.username} follows {self.followed.username}"

    class Meta:
        verbose_name = "User Follow"
        verbose_name_plural = "User Follows"
        # Ensure a user follows another user only once
        unique_together = ('follower', 'followed')
        ordering = ['-created_at']
        # You might add a check constraint in the DB or validation in the form/serializer
        # to prevent users from following themselves.
        # constraints = [
        #     models.CheckConstraint(check=~models.Q(follower=models.F('followed')), name='prevent_self_follow')
        # ] # Requires Django 2.2+