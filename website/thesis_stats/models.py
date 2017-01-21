from django.db import models
import json

class LogEntry(models.Model):
    identifier = models.CharField(max_length=255, db_index=True)
    date = models.DateTimeField(auto_now_add=True)
    last_date = models.CharField(max_length=99)
    cur_date = models.CharField(max_length=99)
    data = models.TextField()

    @property
    def body(self):
        return json.loads(self.data)
