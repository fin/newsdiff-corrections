# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'LogEntry.message_body'
        db.delete_column(u'thesis_stats_logentry', 'message_body')

        # Deleting field 'LogEntry.message_type'
        db.delete_column(u'thesis_stats_logentry', 'message_type')

        # Adding field 'LogEntry.last_date'
        db.add_column(u'thesis_stats_logentry', 'last_date',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=99),
                      keep_default=False)

        # Adding field 'LogEntry.cur_date'
        db.add_column(u'thesis_stats_logentry', 'cur_date',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=99),
                      keep_default=False)

        # Adding field 'LogEntry.data'
        db.add_column(u'thesis_stats_logentry', 'data',
                      self.gf('django.db.models.fields.TextField')(default=''),
                      keep_default=False)


    def backwards(self, orm):

        # User chose to not deal with backwards NULL issues for 'LogEntry.message_body'
        raise RuntimeError("Cannot reverse this migration. 'LogEntry.message_body' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration        # Adding field 'LogEntry.message_body'
        db.add_column(u'thesis_stats_logentry', 'message_body',
                      self.gf('django.db.models.fields.TextField')(),
                      keep_default=False)


        # User chose to not deal with backwards NULL issues for 'LogEntry.message_type'
        raise RuntimeError("Cannot reverse this migration. 'LogEntry.message_type' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration        # Adding field 'LogEntry.message_type'
        db.add_column(u'thesis_stats_logentry', 'message_type',
                      self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True),
                      keep_default=False)

        # Deleting field 'LogEntry.last_date'
        db.delete_column(u'thesis_stats_logentry', 'last_date')

        # Deleting field 'LogEntry.cur_date'
        db.delete_column(u'thesis_stats_logentry', 'cur_date')

        # Deleting field 'LogEntry.data'
        db.delete_column(u'thesis_stats_logentry', 'data')


    models = {
        u'thesis_stats.logentry': {
            'Meta': {'object_name': 'LogEntry'},
            'cur_date': ('django.db.models.fields.CharField', [], {'max_length': '99'}),
            'data': ('django.db.models.fields.TextField', [], {}),
            'date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'identifier': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'last_date': ('django.db.models.fields.CharField', [], {'max_length': '99'})
        }
    }

    complete_apps = ['thesis_stats']
