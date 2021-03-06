
from django.test import TestCase
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry
from django.contrib.admin.sites import LOGIN_FORM_KEY, _encode_post_data
from django.contrib.admin.util import quote
from django.utils.html import escape

# local test models
from .models import Article, CustomArticle, Section, ModelWithStringPrimaryKey

def get_perm(Model, perm):
    """Return the permission object, for the Model"""
    ct = ContentType.objects.get_for_model(Model)
    return Permission.objects.get(content_type=ct,codename=perm)

class AdminViewPermissionsTest(TestCase):
    """Tests for Admin Views Permissions."""
    
    fixtures = ['admin-views-users.xml']
    
    def setUp(self):
        """Test setup."""
        # Setup permissions, for our users who can add, change, and delete. 
        # We can't put this into the fixture, because the content type id
        # and the permission id could be different on each run of the test.
        
        opts = Article._meta
        
        # User who can add Articles
        add_user = User.objects.get(username='adduser')
        add_user.user_permissions.add(get_perm(Article,
            opts.get_add_permission()))
        
        # User who can change Articles
        change_user = User.objects.get(username='changeuser')
        change_user.user_permissions.add(get_perm(Article,
            opts.get_change_permission()))
        
        # User who can delete Articles
        delete_user = User.objects.get(username='deleteuser')
        delete_user.user_permissions.add(get_perm(Article,
            opts.get_delete_permission()))
        
        delete_user.user_permissions.add(get_perm(Section,
            Section._meta.get_delete_permission()))
        
        # login POST dicts
        self.super_login = {'post_data': _encode_post_data({}),
                     LOGIN_FORM_KEY: 1,
                     'username': 'super',
                     'password': 'secret'}
        self.super_email_login = {'post_data': _encode_post_data({}),
                     LOGIN_FORM_KEY: 1,
                     'username': 'super@example.com',
                     'password': 'secret'}
        self.super_email_bad_login = {'post_data': _encode_post_data({}),
                      LOGIN_FORM_KEY: 1,
                      'username': 'super@example.com',
                      'password': 'notsecret'}
        self.adduser_login = {'post_data': _encode_post_data({}),
                     LOGIN_FORM_KEY: 1,
                     'username': 'adduser',
                     'password': 'secret'}
        self.changeuser_login = {'post_data': _encode_post_data({}),
                     LOGIN_FORM_KEY: 1,
                     'username': 'changeuser',
                     'password': 'secret'}
        self.deleteuser_login = {'post_data': _encode_post_data({}),
                     LOGIN_FORM_KEY: 1,
                     'username': 'deleteuser',
                     'password': 'secret'}
        self.joepublic_login = {'post_data': _encode_post_data({}),
                     LOGIN_FORM_KEY: 1,
                     'username': 'joepublic',
                     'password': 'secret'}

    def testTrailingSlashRequired(self):
        """
        If you leave off the trailing slash, app should redirect and add it.
        """
        self.client.post('/test_admin/admin/', self.super_login)
        
        request = self.client.get(
            '/test_admin/admin/admin_views/article/add'
        )
        self.assertRedirects(request,
            '/test_admin/admin/admin_views/article/add/'
        )

    def testLogin(self):
        """
        Make sure only staff members can log in.
        
        Successful posts to the login page will redirect to the orignal url.
        Unsuccessfull attempts will continue to render the login page with 
        a 200 status code.
        """
        # Super User
        request = self.client.get('/test_admin/admin/')
        self.assertEqual(request.status_code, 200)
        login = self.client.post('/test_admin/admin/', self.super_login)
        self.assertRedirects(login, '/test_admin/admin/')
        self.assertFalse(login.context)
        self.client.get('/test_admin/admin/logout/')
        
        # Test if user enters e-mail address
        request = self.client.get('/test_admin/admin/')
        self.assertEqual(request.status_code, 200)
        login = self.client.post('/test_admin/admin/', self.super_email_login)
        self.assertContains(login, "Your e-mail address is not your username")
        # only correct passwords get a username hint
        login = self.client.post('/test_admin/admin/', self.super_email_bad_login)
        self.assertContains(login, "Usernames cannot contain the &#39;@&#39; character")
        new_user = User(username='jondoe', password='secret', email='super@example.com')
        new_user.save()
        # check to ensure if there are multiple e-mail addresses a user doesn't get a 500
        login = self.client.post('/test_admin/admin/', self.super_email_login)
        self.assertContains(login, "Usernames cannot contain the &#39;@&#39; character")
        
        # Add User
        request = self.client.get('/test_admin/admin/')
        self.assertEqual(request.status_code, 200)
        login = self.client.post('/test_admin/admin/', self.adduser_login)
        self.assertRedirects(login, '/test_admin/admin/')
        self.assertFalse(login.context)
        self.client.get('/test_admin/admin/logout/')
        
        # Change User
        request = self.client.get('/test_admin/admin/')
        self.assertEqual(request.status_code, 200)
        login = self.client.post('/test_admin/admin/', self.changeuser_login)
        self.assertRedirects(login, '/test_admin/admin/')
        self.assertFalse(login.context)
        self.client.get('/test_admin/admin/logout/')
        
        # Delete User
        request = self.client.get('/test_admin/admin/')
        self.assertEqual(request.status_code, 200)
        login = self.client.post('/test_admin/admin/', self.deleteuser_login)
        self.assertRedirects(login, '/test_admin/admin/')
        self.assertFalse(login.context)
        self.client.get('/test_admin/admin/logout/')
        
        # Regular User should not be able to login.
        request = self.client.get('/test_admin/admin/')
        self.assertEqual(request.status_code, 200)
        login = self.client.post('/test_admin/admin/', self.joepublic_login)
        self.assertEqual(login.status_code, 200)
        # Login.context is a list of context dicts we just need to check the first one.
        self.assertTrue(login.context[0].get('error_message'))

    def testAddView(self):
        """Test add view restricts access and actually adds items."""
        
        add_dict = {'content': '<p>great article</p>',
                    'date_0': '2008-03-18', 'date_1': '10:54:39',
                    'section': 1}
        
        # Change User should not have access to add articles
        self.client.get('/test_admin/admin/')
        self.client.post('/test_admin/admin/', self.changeuser_login)
        request = self.client.get('/test_admin/admin/admin_views/article/add/')
        self.assertEqual(request.status_code, 403)
        # Try POST just to make sure
        post = self.client.post('/test_admin/admin/admin_views/article/add/', add_dict)
        self.assertEqual(post.status_code, 403)
        self.assertEqual(Article.objects.all().count(), 1)
        self.client.get('/test_admin/admin/logout/')
        
        # Add user may login and POST to add view, then redirect to admin root
        self.client.get('/test_admin/admin/')
        self.client.post('/test_admin/admin/', self.adduser_login)
        post = self.client.post('/test_admin/admin/admin_views/article/add/', add_dict)
        self.assertRedirects(post, '/test_admin/admin/')
        self.assertEqual(Article.objects.all().count(), 2)
        self.client.get('/test_admin/admin/logout/')
        
        # Super can add too, but is redirected to the change list view
        self.client.get('/test_admin/admin/')
        self.client.post('/test_admin/admin/', self.super_login)
        post = self.client.post('/test_admin/admin/admin_views/article/add/', add_dict)
        self.assertRedirects(post, '/test_admin/admin/admin_views/article/')
        self.assertEqual(Article.objects.all().count(), 3)
        self.client.get('/test_admin/admin/logout/')
        
        # Check and make sure that if user expires, data still persists
        post = self.client.post('/test_admin/admin/admin_views/article/add/', add_dict)
        self.assertContains(post, 'Please log in again, because your session has expired.')
        self.super_login['post_data'] = _encode_post_data(add_dict)
        post = self.client.post('/test_admin/admin/admin_views/article/add/', self.super_login)
        self.assertRedirects(post, '/test_admin/admin/admin_views/article/')
        self.assertEqual(Article.objects.all().count(), 4)
        self.client.get('/test_admin/admin/logout/')

    def testChangeView(self):
        """Change view should restrict access and allow users to edit items."""
        
        change_dict = {'content': '<p>edited article</p>',
                    'date_0': '2008-03-18', 'date_1': '10:54:39',
                    'section': 1}
        
        # add user shoud not be able to view the list of article or change any of them
        self.client.get('/test_admin/admin/')
        self.client.post('/test_admin/admin/', self.adduser_login)
        request = self.client.get('/test_admin/admin/admin_views/article/')
        self.assertEqual(request.status_code, 403)
        request = self.client.get('/test_admin/admin/admin_views/article/1/')
        self.assertEqual(request.status_code, 403)
        post = self.client.post('/test_admin/admin/admin_views/article/1/', change_dict)
        self.assertEqual(post.status_code, 403)
        self.client.get('/test_admin/admin/logout/')
        
        # change user can view all items and edit them
        self.client.get('/test_admin/admin/')
        self.client.post('/test_admin/admin/', self.changeuser_login)
        request = self.client.get('/test_admin/admin/admin_views/article/')
        self.assertEqual(request.status_code, 200)
        request = self.client.get('/test_admin/admin/admin_views/article/1/')
        self.assertEqual(request.status_code, 200)
        post = self.client.post('/test_admin/admin/admin_views/article/1/', change_dict)
        self.assertRedirects(post, '/test_admin/admin/admin_views/article/')
        self.assertEqual(Article.objects.get(pk=1).content, '<p>edited article</p>')
        self.client.get('/test_admin/admin/logout/')

    def testCustomModelAdminTemplates(self):
        self.client.get('/test_admin/admin/')
        self.client.post('/test_admin/admin/', self.super_login)
        
        # Test custom change list template with custom extra context
        request = self.client.get('/test_admin/admin/admin_views/customarticle/')
        self.assertEqual(request.status_code, 200)
        self.assertTrue("var hello = 'Hello!';" in request.content)
        self.assertTemplateUsed(request, 'custom_admin/change_list.html')
        
        # Test custom change form template
        request = self.client.get('/test_admin/admin/admin_views/customarticle/add/')
        self.assertTemplateUsed(request, 'custom_admin/change_form.html')
        
        # Add an article so we can test delete and history views
        post = self.client.post('/test_admin/admin/admin_views/customarticle/add/', {
            'content': '<p>great article</p>',
            'date_0': '2008-03-18',
            'date_1': '10:54:39'
        })
        self.assertRedirects(post, '/test_admin/admin/admin_views/customarticle/')
        self.assertEqual(CustomArticle.objects.all().count(), 1)
        
        # Test custom delete and object history templates
        request = self.client.get('/test_admin/admin/admin_views/customarticle/1/delete/')
        self.assertTemplateUsed(request, 'custom_admin/delete_confirmation.html')
        request = self.client.get('/test_admin/admin/admin_views/customarticle/1/history/')
        self.assertTemplateUsed(request, 'custom_admin/object_history.html')
        
        self.client.get('/test_admin/admin/logout/')

    def testCustomAdminSiteTemplates(self):
        from django.contrib import admin
        self.assertEqual(admin.site.index_template, None)
        self.assertEqual(admin.site.login_template, None)
        
        self.client.get('/test_admin/admin/logout/')
        request = self.client.get('/test_admin/admin/')
        self.assertTemplateUsed(request, 'admin/login.html')
        self.client.post('/test_admin/admin/', self.changeuser_login)
        request = self.client.get('/test_admin/admin/')
        self.assertTemplateUsed(request, 'admin/index.html')
        
        self.client.get('/test_admin/admin/logout/')
        admin.site.login_template = 'custom_admin/login.html'
        admin.site.index_template = 'custom_admin/index.html'
        request = self.client.get('/test_admin/admin/')
        self.assertTemplateUsed(request, 'custom_admin/login.html')
        self.assertTrue('Hello from a custom login template' in request.content)
        self.client.post('/test_admin/admin/', self.changeuser_login)
        request = self.client.get('/test_admin/admin/')
        self.assertTemplateUsed(request, 'custom_admin/index.html')
        self.assertTrue('Hello from a custom index template' in request.content)
        
        # Finally, using monkey patching check we can inject custom_context arguments in to index
        original_index = admin.site.index
        def index(*args, **kwargs):
            kwargs['extra_context'] = {'foo': '*bar*'}
            return original_index(*args, **kwargs)
        admin.site.index = index
        request = self.client.get('/test_admin/admin/')
        self.assertTemplateUsed(request, 'custom_admin/index.html')
        self.assertTrue('Hello from a custom index template *bar*' in request.content)
        
        self.client.get('/test_admin/admin/logout/')
        del admin.site.index # Resets to using the original
        admin.site.login_template = None
        admin.site.index_template = None

    def testDeleteView(self):
        """Delete view should restrict access and actually delete items."""
        
        delete_dict = {'post': 'yes'}
        
        # add user shoud not be able to delete articles
        self.client.get('/test_admin/admin/')
        self.client.post('/test_admin/admin/', self.adduser_login)
        request = self.client.get('/test_admin/admin/admin_views/article/1/delete/')
        self.assertEqual(request.status_code, 403)
        post = self.client.post('/test_admin/admin/admin_views/article/1/delete/', delete_dict)
        self.assertEqual(post.status_code, 403)
        self.assertEqual(Article.objects.all().count(), 1)
        self.client.get('/test_admin/admin/logout/')
        
        # Delete user can delete
        self.client.get('/test_admin/admin/')
        self.client.post('/test_admin/admin/', self.deleteuser_login)
        response = self.client.get('/test_admin/admin/admin_views/section/1/delete/')
         # test response contains link to related Article
        self.assertContains(response, "admin_views/article/1/")
        
        response = self.client.get('/test_admin/admin/admin_views/article/1/delete/')
        self.assertEqual(response.status_code, 200)
        post = self.client.post('/test_admin/admin/admin_views/article/1/delete/', delete_dict)
        self.assertRedirects(post, '/test_admin/admin/')
        self.assertEqual(Article.objects.all().count(), 0)
        self.client.get('/test_admin/admin/logout/')

class AdminViewStringPrimaryKeyTest(TestCase):
    fixtures = ['admin-views-users.xml', 'string-primary-key.xml']
    
    def __init__(self, *args):
        super(AdminViewStringPrimaryKeyTest, self).__init__(*args)
        self.pk = """abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ 1234567890 -_.!~*'() ;/?:@&=+$, <>#%" {}|\^[]`"""
    
    def setUp(self):
        self.client.login(username='super', password='secret')
        content_type_pk = ContentType.objects.get_for_model(ModelWithStringPrimaryKey).pk
        LogEntry.objects.log_action(100, content_type_pk, self.pk, self.pk, 2, change_message='')
    
    def tearDown(self):
        self.client.logout()
    
    def test_get_change_view(self):
        "Retrieving the object using urlencoded form of primary key should work"
        response = self.client.get('/test_admin/admin/admin_views/modelwithstringprimarykey/%s/' % quote(self.pk))
        self.assertContains(response, escape(self.pk))
        self.assertEqual(response.status_code, 200)
    
    def test_changelist_to_changeform_link(self):
        "The link from the changelist referring to the changeform of the object should be quoted"
        response = self.client.get('/test_admin/admin/admin_views/modelwithstringprimarykey/')
        should_contain = """<tr class="row1"><th><a href="%s/">%s</a></th></tr>""" % (quote(self.pk), escape(self.pk))
        self.assertContains(response, should_contain)
    
    def test_recentactions_link(self):
        "The link from the recent actions list referring to the changeform of the object should be quoted"
        response = self.client.get('/test_admin/admin/')
        should_contain = """<a href="admin_views/modelwithstringprimarykey/%s/">%s</a>""" % (quote(self.pk), escape(self.pk))
        self.assertContains(response, should_contain)
    
    def test_deleteconfirmation_link(self):
        "The link from the delete confirmation page referring back to the changeform of the object should be quoted"
        response = self.client.get('/test_admin/admin/admin_views/modelwithstringprimarykey/%s/delete/' % quote(self.pk))
        should_contain = """<a href="../../%s/">%s</a>""" % (quote(self.pk), escape(self.pk))
        self.assertContains(response, should_contain)
