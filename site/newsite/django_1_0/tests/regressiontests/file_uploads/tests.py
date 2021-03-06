import os
import errno
import sha
import shutil
import unittest

from django.core.files import temp as tempfile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, client
from django.utils import simplejson

from .models import FileModel, UPLOAD_ROOT, UPLOAD_TO

class FileUploadTests(TestCase):
    def test_simple_upload(self):
        post_data = {
            'name': 'Ringo',
            'file_field': open(__file__),
        }
        response = self.client.post('/file_uploads/upload/', post_data)
        self.assertEqual(response.status_code, 200)

    def test_large_upload(self):
        tdir = tempfile.gettempdir()

        file1 = tempfile.NamedTemporaryFile(suffix=".file1", dir=tdir)
        file1.write('a' * (2 ** 21))
        file1.seek(0)

        file2 = tempfile.NamedTemporaryFile(suffix=".file2", dir=tdir)
        file2.write('a' * (10 * 2 ** 20))
        file2.seek(0)

        # This file contains chinese symbols for a name.
        file3 = open(os.path.join(tdir, 'test_&#20013;&#25991;_Orl\u00e9ans.jpg'.encode('utf-8')), 'w+b')
        file3.write('b' * (2 ** 10))
        file3.seek(0)

        post_data = {
            'name': 'Ringo',
            'file_field1': open(file1.name),
            'file_field2': open(file2.name),
            'file_unicode': file3,
            }

        for key in list(post_data.keys()):
            try:
                post_data[key + '_hash'] = sha.new(post_data[key].read()).hexdigest()
                post_data[key].seek(0)
            except AttributeError:
                post_data[key + '_hash'] = sha.new(post_data[key]).hexdigest()

        response = self.client.post('/file_uploads/verify/', post_data)

        try:
            os.unlink(file3.name)
        except:
            pass

        self.assertEqual(response.status_code, 200)

    def test_dangerous_file_names(self):
        """Uploaded file names should be sanitized before ever reaching the view."""
        # This test simulates possible directory traversal attacks by a
        # malicious uploader We have to do some monkeybusiness here to construct
        # a malicious payload with an invalid file name (containing os.sep or
        # os.pardir). This similar to what an attacker would need to do when
        # trying such an attack.
        scary_file_names = [
            "/tmp/hax0rd.txt",          # Absolute path, *nix-style.
            "C:\\Windows\\hax0rd.txt",  # Absolute path, win-syle.
            "C:/Windows/hax0rd.txt",    # Absolute path, broken-style.
            "\\tmp\\hax0rd.txt",        # Absolute path, broken in a different way.
            "/tmp\\hax0rd.txt",         # Absolute path, broken by mixing.
            "subdir/hax0rd.txt",        # Descendant path, *nix-style.
            "subdir\\hax0rd.txt",       # Descendant path, win-style.
            "sub/dir\\hax0rd.txt",      # Descendant path, mixed.
            "../../hax0rd.txt",         # Relative path, *nix-style.
            "..\\..\\hax0rd.txt",       # Relative path, win-style.
            "../..\\hax0rd.txt"         # Relative path, mixed.
        ]

        payload = []
        for i, name in enumerate(scary_file_names):
            payload.extend([
                '--' + client.BOUNDARY,
                'Content-Disposition: form-data; name="file%s"; filename="%s"' % (i, name),
                'Content-Type: application/octet-stream',
                '',
                'You got pwnd.'
            ])
        payload.extend([
            '--' + client.BOUNDARY + '--',
            '',
        ])

        payload = "\r\n".join(payload)
        r = {
            'CONTENT_LENGTH': len(payload),
            'CONTENT_TYPE':   client.MULTIPART_CONTENT,
            'PATH_INFO':      "/file_uploads/echo/",
            'REQUEST_METHOD': 'POST',
            'wsgi.input':     client.FakePayload(payload),
        }
        response = self.client.request(**r)

        # The filenames should have been sanitized by the time it got to the view.
        recieved = simplejson.loads(response.content)
        for i, name in enumerate(scary_file_names):
            got = recieved["file%s" % i]
            self.assertEqual(got, "hax0rd.txt")

    def test_filename_overflow(self):
        """File names over 256 characters (dangerous on some platforms) get fixed up."""
        name = "%s.txt" % ("f"*500)
        payload = "\r\n".join([
            '--' + client.BOUNDARY,
            'Content-Disposition: form-data; name="file"; filename="%s"' % name,
            'Content-Type: application/octet-stream',
            '',
            'Oops.'
            '--' + client.BOUNDARY + '--',
            '',
        ])
        r = {
            'CONTENT_LENGTH': len(payload),
            'CONTENT_TYPE':   client.MULTIPART_CONTENT,
            'PATH_INFO':      "/file_uploads/echo/",
            'REQUEST_METHOD': 'POST',
            'wsgi.input':     client.FakePayload(payload),
        }
        got = simplejson.loads(self.client.request(**r).content)
        self.assertTrue(len(got['file']) < 256, "Got a long file name (%s characters)." % len(got['file']))

    def test_custom_upload_handler(self):
        # A small file (under the 5M quota)
        smallfile = tempfile.NamedTemporaryFile()
        smallfile.write('a' * (2 ** 21))

        # A big file (over the quota)
        bigfile = tempfile.NamedTemporaryFile()
        bigfile.write('a' * (10 * 2 ** 20))

        # Small file posting should work.
        response = self.client.post('/file_uploads/quota/', {'f': open(smallfile.name)})
        got = simplejson.loads(response.content)
        self.assertTrue('f' in got)

        # Large files don't go through.
        response = self.client.post("/file_uploads/quota/", {'f': open(bigfile.name)})
        got = simplejson.loads(response.content)
        self.assertTrue('f' not in got)

    def test_broken_custom_upload_handler(self):
        f = tempfile.NamedTemporaryFile()
        f.write('a' * (2 ** 21))

        # AttributeError: You cannot alter upload handlers after the upload has been processed.
        self.assertRaises(
            AttributeError,
            self.client.post,
            '/file_uploads/quota/broken/',
            {'f': open(f.name)}
        )

    def test_fileupload_getlist(self):
        file1 = tempfile.NamedTemporaryFile()
        file1.write('a' * (2 ** 23))

        file2 = tempfile.NamedTemporaryFile()
        file2.write('a' * (2 * 2 ** 18))

        file2a = tempfile.NamedTemporaryFile()
        file2a.write('a' * (5 * 2 ** 20))

        response = self.client.post('/file_uploads/getlist_count/', {
            'file1': open(file1.name),
            'field1': 'test',
            'field2': 'test3',
            'field3': 'test5',
            'field4': 'test6',
            'field5': 'test7',
            'file2': (open(file2.name), open(file2a.name))
        })
        got = simplejson.loads(response.content)

        self.assertEqual(got.get('file1'), 1)
        self.assertEqual(got.get('file2'), 2)

class DirectoryCreationTests(unittest.TestCase):
    """
    Tests for error handling during directory creation
    via _save_FIELD_file (ticket #6450)
    """
    def setUp(self):
        self.obj = FileModel()
        if not os.path.isdir(UPLOAD_ROOT):
            os.makedirs(UPLOAD_ROOT)

    def tearDown(self):
        os.chmod(UPLOAD_ROOT, 0o700)
        shutil.rmtree(UPLOAD_ROOT)

    def test_readonly_root(self):
        """Permission errors are not swallowed"""
        os.chmod(UPLOAD_ROOT, 0o500)
        try:
            self.obj.save_testfile_file('foo.txt', SimpleUploadedFile('foo.txt', 'x'))
        except OSError as err:
            self.assertEqual(err.errno, errno.EACCES)
        except:
            self.fail("OSError [Errno %s] not raised" % errno.EACCES)

    def test_not_a_directory(self):
        """The correct IOError is raised when the upload directory name exists but isn't a directory"""
        # Create a file with the upload directory name
        fd = open(UPLOAD_TO, 'w')
        fd.close()
        try:
            self.obj.save_testfile_file('foo.txt', SimpleUploadedFile('foo.txt', 'x'))
        except IOError as err:
            # The test needs to be done on a specific string as IOError
            # is raised even without the patch (just not early enough)
            self.assertEqual(err.args[0],
                              "%s exists and is not a directory" % UPLOAD_TO)
        except:
            self.fail("IOError not raised")
