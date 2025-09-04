from django import forms
from django.contrib.auth.forms import UserCreationForm
from news_app.models import CustomUser, Article, Comment, Category
from django.core.exceptions import ValidationError


class CustomUserRegistrationForm(UserCreationForm):
    """Form for registering a new user with extended fields and validation."""
    ROLE_CHOICES = (
        ('reader', 'Reader'),
        ('journalist', 'Journalist'),
        ('editor', 'Editor'),
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True)
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'role', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        
        # Add help text
        self.fields['username'].help_text = 'Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'
        self.fields['email'].help_text = 'We\'ll never share your email with anyone else.'
        self.fields['role'].help_text = 'Choose your role. You can request role changes later.'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise ValidationError('A user with this email already exists.')
        return email


class ArticleForm(forms.ModelForm):
    """Form for creating or editing articles with custom validation and widgets."""
    
    class Meta:
        model = Article
        fields = [
            'title', 'subtitle', 'content', 'excerpt', 'category', 
            'tags', 'featured_image', 'featured_image_alt',
            'meta_description', 'meta_keywords', 'allow_comments',
            'publisher'
        ]
        
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter article title...'
            }),
            'subtitle': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional subtitle...'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control rich-text-editor',
                'rows': 15,
                'placeholder': 'Write your article content here...'
            }),
            'excerpt': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Brief summary for previews (will be auto-generated if left empty)...'
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter tags separated by commas...'
            }),
            'featured_image': forms.FileInput(attrs={'class': 'form-control'}),
            'featured_image_alt': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Describe the image for accessibility...'
            }),
            'meta_description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'SEO meta description (160 characters max)...'
            }),
            'meta_keywords': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'SEO keywords separated by commas...'
            }),
            'allow_comments': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'publisher': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter publisher choices based on user role
        if self.user:
            if self.user.role == 'journalist':
                self.fields['publisher'].queryset = self.user.affiliated_publishers.all()
                if not self.fields['publisher'].queryset.exists():
                    self.fields['publisher'].empty_label = "No affiliated publishers"
            elif self.user.role == 'editor':
                self.fields['publisher'].queryset = self.user.managed_publishers.all()
        
        # Make category required
        self.fields['category'].empty_label = "Select a category"
        self.fields['category'].queryset = Category.objects.filter(is_active=True)

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if len(title) < 5:
            raise ValidationError('Title must be at least 5 characters long.')
        return title

    def clean_content(self):
        content = self.cleaned_data.get('content')
        if len(content.split()) < 50:
            raise ValidationError('Article content must be at least 50 words long.')
        return content

    def clean_tags(self):
        tags = self.cleaned_data.get('tags', '')
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',')]
            if len(tag_list) > 10:
                raise ValidationError('Maximum 10 tags allowed.')
            if any(len(tag) > 30 for tag in tag_list):
                raise ValidationError('Each tag must be 30 characters or less.')
        return tags


class CommentForm(forms.ModelForm):
    """Comment form for articles"""
    
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Share your thoughts...'
            })
        }

    def clean_content(self):
        content = self.cleaned_data.get('content')
        if len(content.strip()) < 5:
            raise ValidationError('Comment must be at least 5 characters long.')
        return content


class UserProfileForm(forms.ModelForm):
    """User profile editing form"""
    
    class Meta:
        model = CustomUser
        fields = [
            'first_name', 'last_name', 'email', 'bio', 'profile_image',
            'date_of_birth', 'phone_number', 'website', 'location'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Tell us about yourself...'
            }),
            'profile_image': forms.FileInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1234567890'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://yourwebsite.com'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City, Country'
            })
        }

    def clean_bio(self):
        bio = self.cleaned_data.get('bio', '')
        if len(bio) > 500:
            raise ValidationError('Bio must be 500 characters or less.')
        return bio


class SearchForm(forms.Form):
    """Advanced search form"""
    query = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search articles, authors, topics...'
        })
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        empty_label="All categories",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    sort_by = forms.ChoiceField(
        choices=[
            ('relevance', 'Relevance'),
            ('-published_at', 'Newest first'),
            ('published_at', 'Oldest first'),
            ('title', 'Title A-Z'),
            ('-view_count', 'Most viewed'),
            ('-like_count', 'Most liked'),
        ],
        initial='relevance',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
