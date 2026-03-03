from django.contrib.auth.decorators import user_passes_test

def role_required(role_name: str):
    def check(user):
        return user.is_authenticated and getattr(user, 'role', None) == role_name
    return user_passes_test(check, login_url='login')

def roles_required(*role_names: str):
    def check(user):
        return user.is_authenticated and getattr(user, 'role', None) in role_names
    return user_passes_test(check, login_url='login')