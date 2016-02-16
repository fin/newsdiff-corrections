# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'LogEntry'
        db.create_table(u'thesis_stats_logentry', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('identifier', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('date', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('message_type', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('message_body', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal(u'thesis_stats', ['LogEntry'])


    def backwards(self, orm):
        # Deleting model 'LogEntry'
        db.delete_table(u'thesis_stats_logentry')


    models = {
        u'thesis_stats.logentry': {
            'Meta': {'object_name': 'LogEntry'},
            'date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'identifier': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'message_body': ('django.db.models.fields.TextField', [], {}),
            'message_type': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'})
        }
    }

    complete_apps = ['thesis_stats']