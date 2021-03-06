from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.core.exceptions import ValidationError

GENDER_CHOICES = (('M', 'Male'), 
				('F', 'Female'),)

QUESTION_TYPE_CHOICE = (('MC', 'Multiple Choice'),
					('RG', 'Range'),
					('TF', 'True or False'),
					('RA', 'Rating'),)

# Here is the proper way to use the User/UserProfile fields.
# All indexing should be done with the UserProfile field.  To
# access the User object, simply use userProfile.user.

class UserProfile(models.Model):
	user = models.OneToOneField(User, related_name="profile", unique=True)
	age = models.IntegerField(default=21)
	gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
	region = models.CharField(max_length = 20, default="Toronto")
	joinDate = models.DateTimeField(auto_now=True)
	avatarUrl = models.URLField(blank=True, max_length = 500)

	def __unicode__(self):
		return self.user.username

def create_user_profile(sender, instance, created, **kwargs):
	if created:
		profile, created = UserProfile.objects.get_or_create(user=instance)

post_save.connect(create_user_profile, sender=User)



class Question(models.Model):
	asker = models.ForeignKey(UserProfile)
	text = models.CharField(max_length = 200)
	questionType = models.CharField(max_length = 2, choices=QUESTION_TYPE_CHOICE)
	date = models.DateTimeField(auto_now=True)
	related_link = models.URLField(blank=True, max_length= 500)
	option1 = models.CharField(max_length = 50, blank=True)
	option2 = models.CharField(max_length = 50, blank=True)
	option3 = models.CharField(max_length = 50, blank=True)
	option4 = models.CharField(max_length = 50, blank=True)
	option5 = models.CharField(max_length = 50, blank=True)
	replyTo = models.ForeignKey('wildfire.Question', null=True, default=None)

	def __unicode__(self):
		return self.text

class Category(models.Model):
	question = models.ManyToManyField(Question, related_name='categories')
	category = models.CharField(max_length = 20)

	# class Meta:
	# 	unique_together = ('question', 'category')

	def __unicode__(self):
		return self.category

class Answer(models.Model):
	user = models.ForeignKey(UserProfile)
	question = models.ForeignKey(Question, related_name='answers')
	answer = models.IntegerField(default=1)

	# class Meta:
	# 	unique_together = ('question', 'user')

class Connected(models.Model):
	user1 = models.ForeignKey(UserProfile, related_name="%(class)s_1")
	user2 = models.ForeignKey(UserProfile, related_name="%(class)s_2")

	class Meta:
		unique_together = ('user1', 'user2')

	def save(self, *args, **kwargs):
		#calling full_clean to perform model validation
		self.full_clean()
		super(Connected, self).save(*args, **kwargs)

	def clean(self):
		if self.user1 == self.user2:
			raise ValidationError('Connected: user1 should not equal user2')


class TargetedQuestion(models.Model):
	user = models.ForeignKey(UserProfile)
	question = models.ForeignKey(Question)

	class Meta:
		unique_together = ('user', 'question')
