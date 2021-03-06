from __future__ import unicode_literals

import io
import logging
import shutil

from PIL import Image
import PyPDF2
import sh
import yaml
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _

from mayan.apps.storage.utils import NamedTemporaryFile

from ..classes import ConverterBase
from ..exceptions import PageCountError
from ..settings import setting_graphics_backend_config

from ..literals import (
    DEFAULT_PDFTOPPM_DPI, DEFAULT_PDFTOPPM_FORMAT, DEFAULT_PDFTOPPM_PATH,
    DEFAULT_PDFINFO_PATH
)

pdftoppm_path = yaml.load(
    stream=setting_graphics_backend_config.value, Loader=SafeLoader
).get(
    'pdftoppm_path', DEFAULT_PDFTOPPM_PATH
)

try:
    pdftoppm = sh.Command(pdftoppm_path)
except sh.CommandNotFound:
    pdftoppm = None
else:
    pdftoppm_format = '-{}'.format(
        yaml.load(
            stream=setting_graphics_backend_config.value, Loader=SafeLoader
        ).get(
            'pdftoppm_format', DEFAULT_PDFTOPPM_FORMAT
        )
    )

    pdftoppm_dpi = format(
        yaml.load(
            stream=setting_graphics_backend_config.value, Loader=SafeLoader
        ).get(
            'pdftoppm_dpi', DEFAULT_PDFTOPPM_DPI
        )
    )

    pdftoppm = pdftoppm.bake(pdftoppm_format, '-r', pdftoppm_dpi)

pdfinfo_path = yaml.load(
    stream=setting_graphics_backend_config.value, Loader=SafeLoader
).get(
    'pdfinfo_path', DEFAULT_PDFINFO_PATH
)

try:
    pdfinfo = sh.Command(pdfinfo_path)
except sh.CommandNotFound:
    pdfinfo = None

logger = logging.getLogger(__name__)


class Python(ConverterBase):
    def convert(self, *args, **kwargs):
        super(Python, self).convert(*args, **kwargs)

        if self.mime_type == 'application/pdf' and pdftoppm:
            new_file_object = NamedTemporaryFile()
            input_filepath = new_file_object.name
            self.file_object.seek(0)
            shutil.copyfileobj(fsrc=self.file_object, fdst=new_file_object)
            self.file_object.seek(0)
            new_file_object.seek(0)

            image_buffer = io.BytesIO()
            try:
                pdftoppm(
                    input_filepath, f=self.page_number + 1,
                    l=self.page_number + 1, _out=image_buffer
                )
                image_buffer.seek(0)
                return Image.open(image_buffer)
            finally:
                new_file_object.close()

    def detect_orientation(self, page_number):
        # Default rotation: 0 degrees
        result = 0

        # Use different ways depending on the file type
        if self.mime_type == 'application/pdf':
            pdf = PyPDF2.PdfFileReader(self.file_object)
            try:
                result = pdf.getPage(page_number - 1).get('/Rotate', 0)
                if isinstance(result, PyPDF2.generic.IndirectObject):
                    result = result.getObject()
            except Exception as exception:
                self.file_object.seek(0)
                pdf = PyPDF2.PdfFileReader(self.file_object)
                if force_text(exception) == 'File has not been decrypted':
                    # File is encrypted, try to decrypt using a blank
                    # password.
                    try:
                        pdf.decrypt(password=b'')
                    except Exception as exception:
                        logger.error(
                            'Unable to detect PDF orientation; %s', exception
                        )
                else:
                    logger.error(
                        'Unable to detect PDF orientation; %s', exception
                    )
            finally:
                self.file_object.seek(0)

        return result

    def get_page_count(self):
        super(Python, self).get_page_count()

        page_count = 1

        if self.mime_type == 'application/pdf' or self.soffice_file:
            if self.soffice_file:
                file_object = self.soffice_file
            else:
                file_object = self.file_object

            try:
                # Try PyPDF to determine the page number
                pdf_reader = PyPDF2.PdfFileReader(
                    stream=file_object, strict=False
                )
                page_count = pdf_reader.getNumPages()
            except Exception as exception:
                if force_text(exception) == 'File has not been decrypted':
                    # File is encrypted, try to decrypt using a blank
                    # password.
                    file_object.seek(0)
                    pdf_reader = PyPDF2.PdfFileReader(
                        stream=file_object, strict=False
                    )
                    try:
                        pdf_reader.decrypt(password=b'')
                        page_count = pdf_reader.getNumPages()
                    except Exception as exception:
                        file_object.seek(0)
                        if force_text(exception) == 'only algorithm code 1 and 2 are supported':
                            # PDF uses an unsupported encryption
                            # Try poppler-util's pdfinfo
                            process = pdfinfo('-', _in=file_object)
                            page_count = int(
                                filter(
                                    lambda line: line.startswith('Pages:'),
                                    force_text(process.stdout).split('\n')
                                )[0].replace('Pages:', '')
                            )
                            file_object.seek(0)
                            logger.debug(
                                'Document contains %d pages', page_count
                            )
                            return page_count
                        else:
                            error_message = _(
                                'Exception determining PDF page count; %s'
                            ) % exception
                            logger.error(error_message)
                            raise PageCountError(error_message)
                else:
                    error_message = _(
                        'Exception determining PDF page count; %s'
                    ) % exception
                    logger.error(error_message)
                    raise PageCountError(error_message)
            else:
                logger.debug('Document contains %d pages', page_count)
                return page_count
            finally:
                file_object.seek(0)
        else:
            try:
                image = Image.open(self.file_object)
            except IOError as exception:
                error_message = _(
                    'Exception determining page count using Pillow; %s'
                ) % exception
                logger.error(error_message)
                raise PageCountError(error_message)
            finally:
                self.file_object.seek(0)

            try:
                while True:
                    image.seek(image.tell() + 1)
                    page_count += 1
            except EOFError:
                # end of sequence
                pass

            return page_count
