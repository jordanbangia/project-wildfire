from django.forms import widgets
from django.contrib.auth.models import User
from django.db.models import Avg, Count

from rest_framework import serializers

from wildfire.models import UserProfile, Question, Answer, Category, Connected
from wildfire.models import GENDER_CHOICES, QUESTION_TYPE_CHOICE

from wildfire.question_serializer_helper import to_array, to_columns, get_quick_stats


class UserSerializer(serializers.ModelSerializer):
	password = serializers.CharField(write_only=True)
	class Meta:
		model = User
		fields = ('id', 'username', 'email', 'first_name', 'last_name', 'password')
		read_only_fields = ('id')

	def update(self, instance, validated_data):
		instance.username = validated_data.get('username', instance.username)
		instance.email = validated_data.get('email', instance.email)
		instance.first_name = validated_data.get('first_name', instance.first_name)
		instance.last_name = validated_data.get('last_name', instance.last_name)
		if 'password' in validated_data:
			instance.set_password(validated_data['password'])	
		instance.save()
		return instance

	def create(self, validated_data):
		user = User.objects.create(**validated_data)
		user.set_password(validated_data['password'])
		user.save()
		return user

class UserProfileSerializer(serializers.ModelSerializer):
	username = serializers.CharField(source='user.username')
	email = serializers.EmailField(source='user.email')
	first_name = serializers.CharField(source='user.first_name')
	last_name = serializers.CharField(source='user.last_name')
	password = serializers.CharField(source='user.password', write_only=True, required=False)
	age = serializers.IntegerField(required=False)
	region = serializers.CharField(required=False)
	id = serializers.IntegerField()

	class Meta:
		model = UserProfile
		fields = ('id', 'email', 'username', 'first_name', 'last_name', 
			'age', 'gender', 'region', 'joinDate', 'avatarUrl', 'password')
		read_only_fields = ('id', 'joinDate')

	def update(self, instance, validated_data):
		instance.age = validated_data.get('age', instance.age)
		instance.gender = validated_data.get('gender', instance.gender)
		instance.region = validated_data.get('region', instance.region)
		instance.avatarUrl = validated_data.get('avatarUrl', instance.avatarUrl)
		instance.save()
		return instance

class AnswerSerializer(serializers.ModelSerializer):
	user = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())
	question = serializers.PrimaryKeyRelatedField(queryset=Question.objects.all())

	class Meta:
		model = Answer
		fields = ('id', 'user', 'question', 'answer')
		read_only_fields = ('id')

class QuestionSerializer(serializers.ModelSerializer):
	asker = UserProfileSerializer(many=False)
	categories = serializers.StringRelatedField(many=True, required=False)
	answers = AnswerSerializer(many=True, read_only=True)
	link = serializers.CharField(source='related_link', required=False)
	replyTo = serializers.PrimaryKeyRelatedField(queryset=Question.objects.all(), required=False)

	class Meta:
		model = Question
		fields = ('id', 'text', 'questionType', 'date', 'asker', 'categories', 
			'option1', 'option2', 'option3', 'option4', 'option5', 'answers', 'link', 'replyTo')
		read_only_fields = ('id', 'date')

	def validate(self, data):
		options = []
		options.append(data['option1'].lower())
		options.append(data['option2'].lower())
		options.append(data['option3'].lower())
		options.append(data['option4'].lower())
		options.append(data['option5'].lower())

		other = []

		has_duplicates = False
		for i in options:
			if has_duplicates:
				break
			elif i is None or i == "":
				pass
			elif i in other:
				has_duplicates = True
			else:
				other.append(i)

		if has_duplicates:
			print("This question has duplicates: " + str(has_duplicates))
			raise serializers.ValidationError("Options must be unique")
		return data


	def to_representation(self, obj):
		rep = super(serializers.ModelSerializer, self).to_representation(obj)
		rep['options'] = to_array(rep)

		answers = rep['answers']
		request = self.context.get('request', None)
		if request and request.user.is_authenticated():
			rep['isUser'] = True
			answer = Answer.objects.filter(question=rep['id'], user=request.user.profile)
			if answer is not None and answer.count() > 0:
				serializer = AnswerSerializer(answer[0]).data
				rep['usersAnswer'] = serializer
			
			# for answer in answers:
			# 	print("Answer user id: " + str(answer['user']))
			# 	print("Request user id: " + str(request.user.profile.id))
			# 	if answer['user'] == request.user.profile.id:
			# 		rep['isAnswered'] = True
			# 		rep['usersAnswer'] = answer
			# 		break
			# 	else:
			# 		rep['isAnswered'] = False
		else:
			rep['isUser'] = False

		answers = Answer.objects.filter(question=rep['id'])
		if rep['questionType'] == 'RG':
			rep['quick'] = answers.values('answer').aggregate(Avg('answer')).get('answer__avg')
		else:
			rep['quick'] = {
				'option1': answers.filter(answer = 0).count(),
				'option2': answers.filter(answer = 1).count(),
				'option3': answers.filter(answer = 2).count(),
				'option4': answers.filter(answer = 3).count(),
				'option5': answers.filter(answer = 4).count()
			}
		return rep

	def to_internal_value(self, data):
		asker_id = data.get('asker', None)
		if asker_id != None:
			asker = UserProfile.objects.get(pk=asker_id)
			data['asker'] = UserProfileSerializer(asker).data
		data = to_columns(data)
		categories = data.pop('categories', None)			
		data = super(serializers.ModelSerializer, self).to_internal_value(data)
		if categories:
			data['categories'] = categories
		return data

	def create(self, validated_data):
		categories = validated_data.pop('categories', None)
		asker = validated_data.pop('asker', None)
		if asker != None:
			asker = UserProfile.objects.get(pk=asker.pop('id'))
		question = Question.objects.create(asker=asker, **validated_data)
		question.save()

		if categories:
			for category in categories:
				print("Creating category " + category)
				catModel = Category.objects.create(category=category)
				catModel.save()
				print("Saving category")
				catModel.question.add(question)
				print("Added to the question")
		return question


	def update(self, instance, validated_data):
		categories = validated_data.pop('categories', None)

		instance.text = validated_data.get('text', instance.text)
		instance.questionType = validated_data.get('questionType', instance.questionType)
		instance.option1 = validated_data.get('option1', instance.option1)
		instance.option2 = validated_data.get('option2', instance.option2)
		instance.option3 = validated_data.get('option3', instance.option3)
		instance.option4 = validated_data.get('option4', instance.option4)
		instance.option5 = validated_data.get('option5', instance.option5)
		instance.save()

		# for category in categories:
		# 	catModel = Category.objects.create(category=category)
		# 	catModel.save()
		# 	catModel.question.add(instance)

		return instance

		
class StatsSerializer(serializers.BaseSerializer):
	def to_representation(self, obj):
		answers = Answer.objects.filter(question=obj.pk)
		request = self.context.get('request', None)
		connections = Connected.objects.filter(user1=request.user.profile)
		connectedAnswers = answers.filter(user__in = connections.values('user2'))
		if obj.questionType == 'RG':
			return{
				'quick':{
					'avg': answers.values('answer').aggregate(Avg('answer')).get('answer__avg'),
					'responses': answers.values('answer')
				},
				'male':{
					'avg': answers.filter(user__gender = "M").values('answer').aggregate(Avg('answer')).get('answer__avg'),
					'responses': answers.filter(user__gender = "M").values('answer')
				},
				'female':{
					'avg': answers.filter(user__gender = "F").values('answer').aggregate(Avg('answer')).get('answer__avg'),
					'responses': answers.filter(user__gender = "F").values('answer')
				},
				'region': answers.values('user__region').annotate(Avg('answer'))
			}
		else:
			regionStats = answers.values('user__region').annotate(Count('user__region'))
			region1 = answers.filter(answer = 0).values('user__region').annotate(Count('user__region'))
			region2 = answers.filter(answer = 1).values('user__region').annotate(Count('user__region'))
			region3 = answers.filter(answer = 2).values('user__region').annotate(Count('user__region'))
			region4 = answers.filter(answer = 3).values('user__region').annotate(Count('user__region'))
			region5 = answers.filter(answer = 4).values('user__region').annotate(Count('user__region'))
			return{
				'quick':{
					'option1': answers.filter(answer = 0).count(),
					'option2': answers.filter(answer = 1).count(),
					'option3': answers.filter(answer = 2).count(),
					'option4': answers.filter(answer = 3).count(),
					'option5': answers.filter(answer = 4).count()
				},
				'connected':{
					'option1': connectedAnswers.filter(answer = 0).count(),
					'option2': connectedAnswers.filter(answer = 1).count(),
					'option3': connectedAnswers.filter(answer = 2).count(),
					'option4': connectedAnswers.filter(answer = 3).count(),
					'option5': connectedAnswers.filter(answer = 4).count()
				},
				'male':{
					'option1': answers.filter(answer = 0,user__gender = "M").count(),
					'option2': answers.filter(answer = 1,user__gender = "M").count(),
					'option3': answers.filter(answer = 2,user__gender = "M").count(),
					'option4': answers.filter(answer = 3,user__gender = "M").count(),
					'option5': answers.filter(answer = 4,user__gender = "M").count()
				},
				'female':{
					'option1': answers.filter(answer = 0,user__gender = "F").count(),
					'option2': answers.filter(answer = 1,user__gender = "F").count(),
					'option3': answers.filter(answer = 2,user__gender = "F").count(),
					'option4': answers.filter(answer = 3,user__gender = "F").count(),
					'option5': answers.filter(answer = 4,user__gender = "F").count()
				},
				'registered':{
					'option1': answers.filter(answer=0).exclude(user=0).count(),
					'option2': answers.filter(answer=1).exclude(user=0).count(),
					'option3': answers.filter(answer=2).exclude(user=0).count(),
					'option4': answers.filter(answer=3).exclude(user=0).count(),
					'option5': answers.filter(answer=4).exclude(user=0).count()
				},
				'region':{
					'regionTotal': regionStats,
					'option1': region1,
					'option2': region2,
					'option3': region3,
					'option4': region4,
					'option5': region5
				},
				'age':{
					'kids':{
						'option1':answers.filter(answer = 0,user__age__lte=12).count(),
						'option2':answers.filter(answer = 1,user__age__lte=12).count(),
						'option3':answers.filter(answer = 2,user__age__lte=12).count(),
						'option4':answers.filter(answer = 3,user__age__lte=12).count(),
						'option5':answers.filter(answer = 4,user__age__lte=12).count()
					},
					'teens':{
						'option1':answers.filter(answer = 0,user__age__lte=19,user__age__gte=13).count(),
						'option2':answers.filter(answer = 1,user__age__lte=19,user__age__gte=13).count(),
						'option3':answers.filter(answer = 2,user__age__lte=19,user__age__gte=13).count(),
						'option4':answers.filter(answer = 3,user__age__lte=19,user__age__gte=13).count(),
						'option5':answers.filter(answer = 4,user__age__lte=19,user__age__gte=13).count()
					},
					'twenties':{
						'option1':answers.filter(answer = 0,user__age__lte=29,user__age__gte=20).count(),
						'option2':answers.filter(answer = 1,user__age__lte=29,user__age__gte=20).count(),
						'option3':answers.filter(answer = 2,user__age__lte=29,user__age__gte=20).count(),
						'option4':answers.filter(answer = 3,user__age__lte=29,user__age__gte=20).count(),
						'option5':answers.filter(answer = 4,user__age__lte=29,user__age__gte=20).count()
					},
					'thirties':{
						'option1':answers.filter(answer = 0,user__age__lte=39,user__age__gte=30).count(),
						'option2':answers.filter(answer = 1,user__age__lte=39,user__age__gte=30).count(),
						'option3':answers.filter(answer = 2,user__age__lte=39,user__age__gte=30).count(),
						'option4':answers.filter(answer = 3,user__age__lte=39,user__age__gte=30).count(),
						'option5':answers.filter(answer = 4,user__age__lte=39,user__age__gte=30).count()
					},
					'older':{
						'option1':answers.filter(answer = 0,user__age__gte=40).count(),
						'option2':answers.filter(answer = 1,user__age__gte=40).count(),
						'option3':answers.filter(answer = 2,user__age__gte=40).count(),
						'option4':answers.filter(answer = 3,user__age__gte=40).count(),
						'option5':answers.filter(answer = 4,user__age__gte=40).count()
					}
				}
			}

class ConnectionSerializer(serializers.ModelSerializer):
	user1 = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())
	user2 = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())

	class Meta:
		model = Connected
		fields = ('user1', 'user2')