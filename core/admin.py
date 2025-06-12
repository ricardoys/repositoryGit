from django.contrib import admin

from .models import Repositorio, GitUser, Issue, Commit

admin.site.register(Repositorio)
admin.site.register(GitUser)
admin.site.register(Issue)
admin.site.register(Commit)