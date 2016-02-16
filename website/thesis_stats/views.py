# Create your views here.
from .models import LogEntry
from django.http import HttpResponse

def insert(request):
    LogEntry.objects.create(**request.POST)
    return HttpResponse('')

