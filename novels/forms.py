from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm


class LoginForm(forms.Form):
    username = forms.CharField(
        label='Tên tài khoản',
        max_length=150,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Nhập tên tài khoản',
                'autocomplete': 'username',
            }
        )
    )

    password = forms.CharField(
        label='Mật khẩu',
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Nhập mật khẩu',
                'autocomplete': 'current-password',
            }
        )
    )


class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        label='Mật khẩu',
        min_length=6,
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Nhập mật khẩu',
                'autocomplete': 'new-password',
            }
        )
    )

    password_confirm = forms.CharField(
        label='Nhập lại mật khẩu',
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Nhập lại mật khẩu',
                'autocomplete': 'new-password',
            }
        )
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(
                attrs={
                    'placeholder': 'Tên tài khoản',
                    'autocomplete': 'username',
                }
            ),
            'email': forms.EmailInput(
                attrs={
                    'placeholder': 'Email',
                    'autocomplete': 'email',
                }
            ),
        }
        labels = {
            'username': 'Tên tài khoản',
            'email': 'Email',
        }

    def clean_username(self):
        username = self.cleaned_data['username']

        if User.objects.filter(
            username=username
        ).exists():
            raise forms.ValidationError(
                'Tên tài khoản này đã tồn tại.'
            )

        return username

    def clean_email(self):
        email = self.cleaned_data['email']

        if User.objects.filter(
            email=email
        ).exists():
            raise forms.ValidationError(
                'Email này đã được sử dụng.'
            )

        return email

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get(
            'password_confirm'
        )

        if (
            password
            and password_confirm
            and password != password_confirm
        ):
            raise forms.ValidationError(
                'Mật khẩu nhập lại không khớp.'
            )

        return cleaned_data

    def save(self, commit=True):
        user = super().save(
            commit=False
        )

        user.set_password(
            self.cleaned_data['password']
        )

        if commit:
            user.save()

        return user


class UserPasswordChangeForm(
    PasswordChangeForm
):
    old_password = forms.CharField(
        label='Mật khẩu hiện tại',
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Nhập mật khẩu hiện tại',
                'autocomplete': 'current-password',
            }
        )
    )

    new_password1 = forms.CharField(
        label='Mật khẩu mới',
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Nhập mật khẩu mới',
                'autocomplete': 'new-password',
            }
        )
    )

    new_password2 = forms.CharField(
        label='Nhập lại mật khẩu mới',
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Nhập lại mật khẩu mới',
                'autocomplete': 'new-password',
            }
        )
    )


class NovelImportForm(forms.Form):
    source_url = forms.URLField(
        label='URL truyện',
        max_length=500,
        widget=forms.URLInput(
            attrs={
                'class': 'import-input',
                'placeholder': 'Dán URL truyện Mê Truyện Chữ...',
                'autocomplete': 'off',
            }
        )
    )

    action = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

    chapter_number = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                'class': 'chapter-input',
                'min': '1',
                'placeholder': 'Ví dụ: 25',
            }
        )
    )

    chapter_start = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                'class': 'chapter-input',
                'min': '1',
                'placeholder': 'Từ chương',
            }
        )
    )

    chapter_end = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                'class': 'chapter-input',
                'min': '1',
                'placeholder': 'Đến chương',
            }
        )
    )