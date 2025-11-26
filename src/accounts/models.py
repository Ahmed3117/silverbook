from django.contrib.auth.models import AbstractUser
from django.db import models

GOVERNMENT_CHOICES = [
    ('1', 'Cairo'),
    ('2', 'Alexandria'),
    ('3', 'Kafr El Sheikh'),
    ('4', 'Dakahleya'),
    ('5', 'Sharkeya'),
    ('6', 'Gharbeya'),
    ('7', 'Monefeya'),
    ('8', 'Qalyubia'),
    ('9', 'Giza'),
    ('10', 'Bani-Sweif'),
    ('11', 'Fayoum'),
    ('12', 'Menya'),
    ('13', 'Assiut'),
    ('14', 'Sohag'),
    ('15', 'Qena'),
    ('16', 'Luxor'),
    ('17', 'Aswan'),
    ('18', 'Red Sea'),
    ('19', 'Behera'),
    ('20', 'Ismailia'),
    ('21', 'Suez'),
    ('22', 'Port-Said'),
    ('23', 'Damietta'),
    ('24', 'Marsa Matrouh'),
    ('25', 'Al-Wadi Al-Gadid'),
    ('26', 'North Sinai'),
    ('27', 'South Sinai'),
]

USER_TYPE_CHOICES = [
        ('student', 'Student'),
        ('parent', 'Parent'),
        ('teacher', 'Teacher'),
        ('store', 'Store'),
    ]
    
YEAR_CHOICES = [
        ('first-secondary', 'First Secondary'),
        ('second-secondary', 'Second Secondary'),
        ('third-secondary', 'Third Secondary'),
    ]

DIVISION_CHOICES = [
    ('عام', 'عام'),
    ('علمى', 'علمى'),
    ('أدبي', 'أدبي'),
    ('علمى علوم', 'علمى علوم'),
    ('علمى رياضة', 'علمى رياضة'),

]

class UserProfileImage(models.Model):
    image = models.ImageField(upload_to='profile_images/')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile Image {self.id}"
    
    class Meta:
        ordering = ['-created_at'] 


class User(AbstractUser):
    name = models.CharField(max_length=100)
    otp = models.CharField(max_length=6, null=True, blank=True)
    otp_created_at = models.DateTimeField(null=True, blank=True)
    email = models.EmailField(blank=True, null=True, max_length=254)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default="student", null=True, blank=True)
    parent_phone = models.CharField(max_length=20, null=True, blank=True, help_text="Only applicable for students")
    year = models.CharField(
        max_length=20,
        choices=YEAR_CHOICES,
        null=True,
        blank=True,
        help_text="Only applicable for students"
    )
    division = models.CharField(
        max_length=20,
        choices=DIVISION_CHOICES,
        null=True,
        blank=True
    )
    government = models.CharField(choices=GOVERNMENT_CHOICES, max_length=2, null=True, blank=True)
    user_profile_image = models.ForeignKey(
        UserProfileImage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    created_at = models.DateTimeField(auto_now_add=True,null=True, blank=True)

    def __str__(self):
        return self.name if self.name else self.username
    
    def save(self, *args, **kwargs):
        """Validate unique name for teachers before saving"""
        self.validate_teacher_name_unique()
        super().save(*args, **kwargs)
    
    def validate_teacher_name_unique(self):
        """Ensure teacher names are unique among users with user_type='teacher'"""
        from django.core.exceptions import ValidationError
        
        if self.user_type == 'teacher':
            # Build query to check for duplicate teacher names
            query = User.objects.filter(
                user_type='teacher',
                name=self.name
            )
            
            # Exclude current instance if updating
            if self.pk:
                query = query.exclude(pk=self.pk)
            
            # Check if duplicate exists
            if query.exists():
                raise ValidationError({
                    'name': f"A teacher with the name '{self.name}' already exists. Teacher names must be unique."
                })
    
    class Meta:
        ordering = ['-created_at']









