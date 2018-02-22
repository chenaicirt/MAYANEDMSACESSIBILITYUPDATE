# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import time

from django.test import override_settings
from django.utils.encoding import force_text

from django_downloadview import assert_download_response
from rest_framework import status

from rest_api.tests import BaseAPITestCase

from .literals import (
    TEST_DOCUMENT_DESCRIPTION_EDITED, TEST_DOCUMENT_FILENAME,
    TEST_DOCUMENT_PATH, TEST_DOCUMENT_TYPE_LABEL,
    TEST_DOCUMENT_TYPE_LABEL_EDITED, TEST_DOCUMENT_VERSION_COMMENT_EDITED,
    TEST_SMALL_DOCUMENT_FILENAME, TEST_SMALL_DOCUMENT_PATH
)
from ..models import Document, DocumentType
from ..permissions import (
    permission_document_create, permission_document_download,
    permission_document_delete, permission_document_edit,
    permission_document_new_version, permission_document_properties_edit,
    permission_document_restore, permission_document_trash,
    permission_document_view, permission_document_type_create,
    permission_document_type_delete, permission_document_type_edit,
    permission_document_version_revert, permission_document_version_view
)


class DocumentTypeAPITestCase(BaseAPITestCase):
    def setUp(self):
        super(DocumentTypeAPITestCase, self).setUp()
        self.admin_user = get_user_model().objects.create_superuser(
            username=TEST_ADMIN_USERNAME, email=TEST_ADMIN_EMAIL,
            password=TEST_ADMIN_PASSWORD
        )

        self.client.login(
            username=TEST_ADMIN_USERNAME, password=TEST_ADMIN_PASSWORD
        )

    def tearDown(self):
        self.admin_user.delete()
        super(DocumentTypeAPITestCase, self).tearDown()

    def test_document_type_create(self):
        self.assertEqual(DocumentType.objects.all().count(), 0)

        response = self.client.post(
            reverse('rest_api:documenttype-list'), data={
                'label': TEST_DOCUMENT_TYPE_LABEL
            }
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(DocumentType.objects.all().count(), 1)
        self.assertEqual(
            DocumentType.objects.all().first().label, TEST_DOCUMENT_TYPE_LABEL
        )

    def test_document_type_edit_via_put(self):
        document_type = DocumentType.objects.create(
            label=TEST_DOCUMENT_TYPE_LABEL
        )
        response = self._request_document_type_put()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_document_type_edit_via_put_with_access(self):
        self.document_type = DocumentType.objects.create(
            label=TEST_DOCUMENT_TYPE_LABEL
        )
        self.grant_access(
            permission=permission_document_type_edit, obj=self.document_type
        )
        response = self._request_document_type_put()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document_type.refresh_from_db()
        self.assertEqual(
            self.document_type.label, TEST_DOCUMENT_TYPE_LABEL_EDITED
        )

    def _request_document_type_patch(self):
        return self.patch(
            viewname='rest_api:documenttype-detail', args=(
                self.document_type.pk,
            ), data={'label': TEST_DOCUMENT_TYPE_LABEL_EDITED}
        )

    def test_document_type_edit_via_patch_no_permission(self):
        self.document_type = DocumentType.objects.create(
            label=TEST_DOCUMENT_TYPE_LABEL
        )
        response = self._request_document_type_patch()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_document_type_edit_via_patch(self):
        document_type = DocumentType.objects.create(
            label=TEST_DOCUMENT_TYPE_LABEL
        )
        self.grant_access(
            permission=permission_document_type_edit, obj=self.document_type
        )

        document_type = DocumentType.objects.get(pk=document_type.pk)
        self.assertEqual(document_type.label, TEST_DOCUMENT_TYPE_LABEL_EDITED)

    def test_document_type_delete(self):
        document_type = DocumentType.objects.create(
            label=TEST_DOCUMENT_TYPE_LABEL
        )

        response = self._request_document_type_delete()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_document_type_delete_with_access(self):
        self.document_type = DocumentType.objects.create(
            label=TEST_DOCUMENT_TYPE_LABEL
        )
        self.grant_access(
            permission=permission_document_type_delete, obj=self.document_type
        )
        response = self._request_document_type_delete()
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(DocumentType.objects.all().count(), 0)


@override_settings(OCR_AUTO_OCR=False)
class DocumentAPITestCase(BaseAPITestCase):
    def setUp(self):
        super(DocumentAPITestCase, self).setUp()
        self.admin_user = get_user_model().objects.create_superuser(
            username=TEST_ADMIN_USERNAME, email=TEST_ADMIN_EMAIL,
            password=TEST_ADMIN_PASSWORD
        )

        self.client.login(
            username=TEST_ADMIN_USERNAME, password=TEST_ADMIN_PASSWORD
        )

        self.document_type = DocumentType.objects.create(
            label=TEST_DOCUMENT_TYPE_LABEL
        )

    def tearDown(self):
        self.admin_user.delete()
        self.document_type.delete()
        super(DocumentAPITestCase, self).tearDown()

    def _create_document(self):
        with open(TEST_SMALL_DOCUMENT_PATH) as file_object:
            self.document = self.document_type.new_document(
                file_object=file_object,
                label=TEST_SMALL_DOCUMENT_FILENAME
            )

        # For compatibility
        return self.document

    def test_document_upload(self):
        with open(TEST_DOCUMENT_PATH) as file_descriptor:
            response = self.client.post(
                reverse('rest_api:document-list'), {
                    'document_type': self.document_type.pk,
                    'file': file_descriptor
                }
            )

    def test_document_upload_no_permission(self):
        response = self._request_document_upload()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_document_upload_with_access(self):
        self.grant_access(
            permission=permission_document_create, obj=self.document_type
        )
        response = self._request_document_upload()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Document.objects.count(), 1)

        document = Document.objects.first()

        self.assertEqual(document.pk, document_data['id'])

        self.assertEqual(document.versions.count(), 1)

        self.assertEqual(document.exists(), True)
        self.assertEqual(document.size, 272213)

        self.assertEqual(document.file_mimetype, 'application/pdf')
        self.assertEqual(document.file_mime_encoding, 'binary')
        self.assertEqual(document.label, TEST_DOCUMENT_FILENAME)
        self.assertEqual(
            document.checksum,
            'c637ffab6b8bb026ed3784afdb07663fddc60099853fae2be93890852a69ecf3'
        )
        self.assertEqual(document.page_count, 47)

    def test_document_new_version_upload(self):
        document = self._create_document()

        # Artifical delay since MySQL doesn't store microsecond data in
        # timestamps. Version timestamp is used to determine which version
        # is the latest.
        time.sleep(1)
        with open(TEST_DOCUMENT_PATH) as file_descriptor:
            response = self.client.post(
                reverse(
                    'rest_api:document-version-list', args=(document.pk,)
                ), {
                    'comment': '',
                    'file': file_descriptor,
                }
            )

    def test_document_new_version_upload_no_permission(self):
        self._create_document()
        response = self._request_document_new_version_upload()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_document_new_version_upload_with_access(self):
        self._create_document()
        self.grant_access(
            permission=permission_document_new_version, obj=self.document
        )
        response = self._request_document_new_version_upload()
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        self.assertEqual(document.versions.count(), 2)
        self.assertEqual(document.exists(), True)
        self.assertEqual(document.size, 272213)
        self.assertEqual(document.file_mimetype, 'application/pdf')
        self.assertEqual(document.file_mime_encoding, 'binary')
        self.assertEqual(
            document.checksum,
            'c637ffab6b8bb026ed3784afdb07663fddc60099853fae2be93890852a69ecf3'
        )
        self.assertEqual(document.page_count, 47)

    def test_document_version_revert(self):
        document = self._create_document()

        # Needed by MySQL as milliseconds value is not store in timestamp field
        time.sleep(1)

        with open(TEST_DOCUMENT_PATH) as file_object:
            document.new_version(file_object=file_object)

        self.assertEqual(document.versions.count(), 2)

    def test_document_version_revert_no_permission(self):
        self._create_document()
        self._create_new_version()
        response = self._request_document_version_revert()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_document_version_revert_with_access(self):
        self._create_document()
        self._create_new_version()
        self.grant_access(
            permission=permission_document_version_revert, obj=self.document
        )
        response = self._request_document_version_revert()
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.document.versions.count(), 1)
        self.assertEqual(
            self.document.versions.first(), self.document.latest_version
        )

        # Needed by MySQL as milliseconds value is not store in timestamp field
        time.sleep(1)

    def test_document_version_list_no_permission(self):
        self._create_document()
        self._create_new_version()
        response = self._request_document_version_list()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_document_version_list_with_access(self):
        self._create_document()
        self._create_new_version()
        self.grant_access(
            permission=permission_document_version_view, obj=self.document
        )
        response = self._request_document_version_list()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['results'][1]['checksum'],
            document.latest_version.checksum
        )

    def _request_document_download(self):
        return self.get(
            viewname='rest_api:document-download', args=(self.document.pk,)
        )

    def test_document_download_no_permission(self):
        self._create_document()
        response = self._request_document_download()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_document_download_with_access(self):
        self._create_document()
        self.grant_access(
            permission=permission_document_download, obj=self.document
        )

        with document.open() as file_object:
            assert_download_response(
                self, response, content=file_object.read(),
                basename=TEST_SMALL_DOCUMENT_FILENAME,
                mime_type='{}; charset=utf-8'.format(document.file_mimetype)
            )

    def _request_document_version_download(self):
        return self.get(
            viewname='rest_api:documentversion-download', args=(
                self.document.pk, self.document.latest_version.pk,
            )
        )

    def test_document_version_download_no_permission(self):
        self._create_document()
        response = self._request_document_version_download()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_document_version_download_with_access(self):
        self._create_document()
        self.grant_access(
            permission=permission_document_download, obj=self.document
        )

        with latest_version.open() as file_object:
            assert_download_response(
                self, response, content=file_object.read(),
                basename=force_text(latest_version),
                mime_type='{}; charset=utf-8'.format(document.file_mimetype)
            )

    def test_document_version_download_preserve_extension(self):
        document = self._create_document()

        latest_version = document.latest_version
        response = self.client.get(
            reverse(
                'rest_api:documentversion-download',
                args=(document.pk, latest_version.pk,)
            ), data={'preserve_extension': True}
        )

        with latest_version.open() as file_object:
            assert_download_response(
                self, response, content=file_object.read(),
                basename=latest_version.get_rendered_string(
                    preserve_extension=True
                ), mime_type='{}; charset=utf-8'.format(
                    document.file_mimetype
                )
            )

    def test_document_version_edit_via_patch(self):
        self._create_document()
        self.grant_access(
            permission=permission_document_edit, obj=self.document
        )
        response = self._request_document_version_edit_via_patch()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.latest_version.refresh_from_db()
        self.assertEqual(self.document.versions.count(), 1)
        self.assertEqual(
            self.document.latest_version.comment,
            TEST_DOCUMENT_VERSION_COMMENT_EDITED
        )

    def test_document_version_edit_via_put(self):
        self._create_document()
        response = self._request_document_version_edit_via_put()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_document_version_edit_via_put_with_access(self):
        self._create_document()
        self.grant_access(
            permission=permission_document_edit, obj=self.document
        )
        response = self._request_document_version_edit_via_put()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.latest_version.refresh_from_db()
        self.assertEqual(self.document.versions.count(), 1)
        self.assertEqual(
            self.document.latest_version.comment,
            TEST_DOCUMENT_VERSION_COMMENT_EDITED
        )

    def _request_document_description_edit_via_patch(self):
        return self.patch(
            viewname='rest_api:document-detail', args=(self.document.pk,),
            data={'description': TEST_DOCUMENT_DESCRIPTION_EDITED}
        )

    def test_document_description_edit_via_patch_no_permission(self):
        self._create_document()
        response = self._request_document_description_edit_via_patch()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_document_description_edit_via_patch_with_access(self):
        self._create_document()
        response = self.client.patch(
            reverse(
                'rest_api:document-detail',
                args=(self.document.pk,)
            ), data={'description': TEST_DOCUMENT_DESCRIPTION_EDITED}
        )
        response = self._request_document_description_edit_via_patch()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.refresh_from_db()
        self.assertEqual(
            self.document.description,
            TEST_DOCUMENT_DESCRIPTION_EDITED
        )

    def test_document_comment_edit_via_put(self):
        self._create_document()
        response = self._request_document_description_edit_via_put()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_document_description_edit_via_put_with_access(self):
        self._create_document()
        self.grant_access(
            permission=permission_document_properties_edit, obj=self.document
        )
        response = self._request_document_description_edit_via_put()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.refresh_from_db()
        self.assertEqual(
            self.document.description,
            TEST_DOCUMENT_DESCRIPTION_EDITED
        )


@override_settings(OCR_AUTO_OCR=False)
class TrashedDocumentAPITestCase(BaseAPITestCase):
    def setUp(self):
        super(TrashedDocumentAPITestCase, self).setUp()
        self.admin_user = get_user_model().objects.create_superuser(
            username=TEST_ADMIN_USERNAME, email=TEST_ADMIN_EMAIL,
            password=TEST_ADMIN_PASSWORD
        )

        self.client.login(
            username=TEST_ADMIN_USERNAME, password=TEST_ADMIN_PASSWORD
        )

        self.document_type = DocumentType.objects.create(
            label=TEST_DOCUMENT_TYPE_LABEL
        )

    def tearDown(self):
        self.admin_user.delete()
        self.document_type.delete()
        super(TrashedDocumentAPITestCase, self).tearDown()

    def _create_document(self):
        with open(TEST_SMALL_DOCUMENT_PATH) as file_object:
            document = self.document_type.new_document(
                file_object=file_object,
            )

    def _request_document_move_to_trash(self):
        return self.delete(
            viewname='rest_api:document-detail', args=(self.document.pk,)
        )

    def test_document_move_to_trash_no_permission(self):
        self._create_document()
        response = self._request_document_move_to_trash()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_document_move_to_trash_with_access(self):
        self._create_document()
        self.grant_access(
            permission=permission_document_trash, obj=self.document
        )

        self.assertEqual(Document.objects.count(), 0)
        self.assertEqual(Document.trash.count(), 1)

    def _request_trashed_document_delete_view(self):
        return self.delete(
            viewname='rest_api:trasheddocument-detail', args=(self.document.pk,)
        )

    def test_trashed_document_delete_from_trash_no_access(self):
        self._create_document()
        self.document.delete()
        response = self._request_trashed_document_delete_view()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Document.objects.count(), 0)
        self.assertEqual(Document.trash.count(), 1)

    def test_trashed_document_delete_from_trash_with_access(self):
        self._create_document()
        self.document.delete()
        self.grant_access(permission=permission_document_delete, obj=self.document)
        response = self._request_trashed_document_delete_view()
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Document.objects.count(), 0)
        self.assertEqual(Document.trash.count(), 0)

    def _request_trashed_document_detail_view(self):
        return self.get(
            viewname='rest_api:trasheddocument-detail', args=(self.document.pk,)
        )

    def test_trashed_document_detail_view_no_access(self):
        self._create_document()
        self.document.delete()
        response = self._request_trashed_document_detail_view()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse('uuid' in response.data)

    def test_trashed_document_detail_view_with_access(self):
        self._create_document()
        self.document.delete()
        self.grant_access(permission=permission_document_view, obj=self.document)
        response = self._request_trashed_document_detail_view()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['uuid'], force_text(self.document.uuid))

    def _request_trashed_document_list_view(self):
        return self.get(
            viewname='rest_api:trasheddocument-list'
        )

    def test_trashed_document_list_view_no_access(self):
        self._create_document()
        self.document.delete()
        response = self._request_trashed_document_list_view()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_trashed_document_list_view_with_access(self):
        self._create_document()
        self.document.delete()
        self.grant_access(
            permission=permission_document_view, obj=self.document
        )
        response = self._request_trashed_document_list_view()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['results'][0]['uuid'], force_text(self.document.uuid)
        )

    def _request_trashed_document_restore_view(self):
        return self.post(
            viewname='rest_api:trasheddocument-restore', args=(self.document.pk,)
        )

    def test_trashed_document_restore_no_access(self):
        self._create_document()
        self.document.delete()
        response = self._request_trashed_document_restore_view()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Document.trash.count(), 1)
        self.assertEqual(Document.objects.count(), 0)

    def test_trashed_document_restore_with_access(self):
        self._create_document()
        self.document.delete()
        self.grant_access(permission=permission_document_restore, obj=self.document)
        response = self._request_trashed_document_restore_view()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Document.trash.count(), 0)
        self.assertEqual(Document.objects.count(), 1)
