"""
 url handlers
"""

import re, time, json, logging, hashlib, base64, asyncio
from www.markdown2 import markdown
from aiohttp import web
from www.webf import get, post
from www.models import User, Comment, Blog, next_id
from www.config import configs
from www.apis import ApiError, ApiValueError, ApiResourceNotFoundError, ApiPermissionError

COOKIE_NAME = 'awesession'
# _COOKIE_KEY = configs.session.secret
_COOKIE_KEY = 'Awesome'


def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise ApiPermissionError()


def get_page_index(page):
    p = 1
    try:
        p = int(page)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p


def text2html(text):
    lines = lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)


def user2cookie(user, max_age):
    """
    Generate cookie str by user.
    :param user:
    :param max_age:
    :return:
    """

    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    li = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(li)


async def cookie2user(cookie):
    """
    Parse cookie and load user if cookie is valid.
    :param cookie:
    :return:
    """

    if not cookie:
        return None
    try:
        li = cookie.split('-')
        if len(li) != 3:
            return None
        uid, expires, sha1 = li
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '********'
        return user
    except Exception as e:
        logging.exception(e)
        return None


@get('/')
async def index(request):
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed' \
                'do eiusmod tempor incididunt ut labore et dolore magna aliqua.'

    blogs = [
        Blog(id='1', name='Test Blog', summary=summary, created_at=time.time() - 120),
        Blog(id='2', name='Something New', summary=summary, created_at=time.time() - 3600),
        Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time() - 7200)
    ]

    return {
        '__template__': 'blogs.html',
        'blogs': blogs
    }


@get('/blog/{blog_id}')
async def get_blog(blog_id):
    blog = await Blog.find(blog_id)
    comments = await Comment.find_all('blog_id=?', [blog_id], orderBy='created_at DESC')
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = markdown(blog.content)
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }


@get('/register')
def register():
    return {
        '__template__': 'register.html'
    }


@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }


@post('/api/authenticate')
async def authenticate(*, email, passwd):
    if not email:
        raise ApiValueError('email', 'Invalid email.')
    if not passwd:
        raise ApiValueError('passwd', 'Invalid password.')
    users = await User.find_all('email=?', [email])
    if len(users) == 0:
        return ApiValueError('email', 'Email not exist.')
    user = users[0]
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise ApiValueError('passwd', 'Invalid password.')
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r


@get('/manage/blogs/create')
async def manage_create_blog():
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs'
    }


_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')


@post('/api/users')
async def api_register_user(*, email, name, passwd):
    if not name or not name.strip():
        raise ApiValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise ApiValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise ApiValueError('passwd')
    users = await User.find_all('email=?', [email])
    if len(users) > 0:
        raise ApiError('register:failed', 'email', 'Email is already in use.')
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    # user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),
    #             image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    user = User()
    user.id = uid
    user.name = name.strip()
    user.email = email
    user.passwd = hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest()
    user.image = 'http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest()
    await user.save()
    # make session cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '********'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


@get('/api/blogs/{blog_id}')
async def api_get_blog(*, blog_id):
    blog = await Blog.find(blog_id)
    return blog


@post('/api/blogs')
async def api_create_blog(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise ApiValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise ApiValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise ApiValueError('content', 'content cannot be empty.')
    # blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
    blog = Blog()
    blog.user_id = request.__user__.id
    blog.user_name = request.__user__.name
    blog.user_image = request.__user__.image
    blog.name = name.strip()
    blog.summary = summary.strip()
    blog.content = content.strip()
    await blog.save()
    return blog
