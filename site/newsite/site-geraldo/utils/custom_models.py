from google.appengine.ext import db

class CustomModel(db.Model):
    _query = None

    @property
    def id(self):
        return self.key().id()

    def __unicode__(self):
        try:
            return str(str(self))
        except TypeError:
            return 'not defined'

    @classmethod
    def get_query(cls):
        if not cls._query:
            cls._query = db.Query(cls)
        return cls._query

    @classmethod
    def create_or_update(cls, **kwargs):
        values = 'values' in kwargs and kwargs.pop('values') or {}

        q = cls.all()

        for k, v in list(kwargs.items()):
            q = q.filter(k+' =', v)

        if q.count():
            obj = q[0]
        else:
            obj = cls()

            for k, v in list(kwargs.items()):
                setattr(obj, k, v)

        for k, v in list(values.items()):
            setattr(obj, k, v)

        obj.put()

        return obj

    @classmethod
    def get_by_field(cls, field, value):
        return db.Query(cls).filter(field+' =', value).get()

    def save(self):
        return self.put()

