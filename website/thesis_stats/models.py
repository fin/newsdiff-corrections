from django.db import models
import json

class LogEntry(models.Model):
    identifier = models.CharField(max_length=255, db_index=True)
    date = models.DateTimeField(auto_now_add=True)
    message_type = models.CharField(max_length=255, db_index=True)
    message_body = models.TextField()

    @property
    def body(self):
        return json.loads(self.message_body)
