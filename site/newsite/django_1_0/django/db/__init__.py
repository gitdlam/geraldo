import os
from django.conf import settings
from django.core import signals
from django.core.exceptions import ImproperlyConfigured
from django.dispatch import dispatcher
from django.utils.functional import curry

__all__ = ('backend', 'connection', 'DatabaseError', 'IntegrityError')

if not settings.DATABASE_ENGINE:
    settings.DATABASE_ENGINE = 'dummy'

try:
    # Most of the time, the database backend will be one of the official
    # backends that ships with Django, so look there first.
    _import_path = 'django.db.backends.'
    backend = __import__('%s%s.base' % (_import_path, settings.DATABASE_ENGINE), {}, {}, [''])
    creation = __import__('%s%s.creation' % (_import_path, settings.DATABASE_ENGINE), {}, {}, [''])
except ImportError as e:
    # If the import failed, we might be looking for a database backend
    # distributed external to Django. So we'll try that next.
    try:
        _import_path = ''
        backend = __import__('%s.base' % settings.DATABASE_ENGINE, {}, {}, [''])
        creation = __import__('%s.creation' % settings.DATABASE_ENGINE, {}, {}, [''])
    except ImportError as e_user:
        # The database backend wasn't found. Display a helpful error message
        # listing all possible (built-in) database backends.
        backend_dir = os.path.join(__path__[0], 'backends')
        available_backends = [f for f in os.listdir(backend_dir) if not f.startswith('_') and not f.startswith('.') and not f.endswith('.py') and not f.endswith('.pyc')]
        available_backends.sort()
        if settings.DATABASE_ENGINE not in available_backends:
            raise ImproperlyConfigured("%r isn't an available database backend. Available options are: %s" % \
                (settings.DATABASE_ENGINE, ", ".join(map(repr, available_backends))))
        else:
            raise # If there's some other error, this must be an error in Django itself.

def _import_database_module(import_path='', module_name=''):
    """Lazily import a database module when requested."""
    return __import__('%s%s.%s' % (import_path, settings.DATABASE_ENGINE, module_name), {}, {}, [''])

# We don't want to import the introspect module unless someone asks for it, so
# lazily load it on demmand.
get_introspection_module = curry(_import_database_module, _import_path, 'introspection')

def get_creation_module():
    return creation

# We want runshell() to work the same way, but we have to treat it a
# little differently (since it just runs instead of returning a module like
# the above) and wrap the lazily-loaded runshell() method.
runshell = lambda: _import_database_module(_import_path, "client").runshell()

# Convenient aliases for backend bits.
connection = backend.DatabaseWrapper(**settings.DATABASE_OPTIONS)
DatabaseError = backend.DatabaseError
IntegrityError = backend.IntegrityError

# Register an event that closes the database connection
# when a Django request is finished.
dispatcher.connect(connection.close, signal=signals.request_finished)

# Register an event that resets connection.queries
# when a Django request is started.
def reset_queries():
    connection.queries = []
dispatcher.connect(reset_queries, signal=signals.request_started)

# Register an event that rolls back the connection
# when a Django request has an exception.
def _rollback_on_exception():
    from django.db import transaction
    transaction.rollback_unless_managed()
dispatcher.connect(_rollback_on_exception, signal=signals.got_request_exception)
