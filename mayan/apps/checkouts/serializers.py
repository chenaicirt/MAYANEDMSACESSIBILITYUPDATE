from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers

from mayan.apps.acls.models import AccessControlList
from mayan.apps.documents.models import Document
from mayan.apps.documents.serializers import DocumentSerializer

from .models import DocumentCheckout
from .permissions import permission_document_check_out


class DocumentCheckoutSerializer(serializers.ModelSerializer):
    document = DocumentSerializer()

    class Meta:
        fields = ('document',)
        model = DocumentCheckout


class NewDocumentCheckoutSerializer(serializers.ModelSerializer):
    block_new_version = serializers.BooleanField()
    document_pk = serializers.IntegerField(
        help_text=_('Primary key of the document to be checked out.'),
        write_only=True
    )

    expiration_datetime = serializers.DateTimeField()

    class Meta:
        fields = (
            'block_new_version', 'document', 'document_pk',
            'expiration_datetime', 'id'
        )
        model = DocumentCheckout
        read_only_fields = ('document',)
        write_only_fields = ('document_pk',)

    def create(self, validated_data):
        document = Document.objects.get(pk=validated_data.pop('document_pk'))

        AccessControlList.objects.check_access(
            obj=document, permissions=permission_document_check_out,
            user=self.context['request'].user
        )

        validated_data['document'] = document
        validated_data['user'] = self.context['request'].user
        return super(NewDocumentCheckoutSerializer, self).create(
            validated_data
        )
