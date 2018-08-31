import psycopg2
from flask import Flask, render_template, request, redirect, url_for
from flask import jsonify, flash, session as login_session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Categories, Users, Items
from datetime import datetime
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import json
from flask import make_response
import requests
from flask_oauth import OAuth

app = Flask(__name__)
app.secret_key = '123456'
oauth = OAuth()
token_param_link = 'https://www.googleapis.com/auth/userinfo.email'

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']

CLIENT_SECRET = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_secret']


engine = create_engine("postgresql+psycopg2://apps:udacity@localhost/catalog")
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

google = oauth.remote_app(
    'google',
    base_url='https://www.google.com/accounts/',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    request_token_url=None,
    request_token_params={'scope': token_param_link, 'response_type': 'code'},
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_method='POST',
    access_token_params={'grant_type': 'authorization_code'},
    consumer_key=CLIENT_ID,
    consumer_secret=CLIENT_SECRET)


def get_categories():
    categories = session.query(Categories).all()
    return categories


def get_latest_items():
    items = session.query(Items, Categories).\
                    join(Categories).order_by(Items.creation_date.desc()).\
                    limit(9)
    return items


def create_user(name):
    """
       Function to create a new user
       Parameter: Name - name of the new user
       Return the User Id
    """
    try:
        user = session.query(Users).filter_by(name=name).one()
    except:
        new_user = Users(name=name)
        session.add(new_user)
        session.commit()

    user = session.query(Users).filter_by(name=name).one()

    return user.id


def get_session_user_id():
    try:
        session_user_id = login_session['user_id']
    except:
        session_user_id = None

    return session_user_id


def get_session_token():
    try:
        session_token = login_session['access_token']
    except:
        session_token = None

    return session_token


@app.route('/login')
def login():
    callback = url_for('authorized', _external=True)
    return google.authorize(callback=callback)


@app.route('/logout')
def logout():
    login_session['access_token'] = None
    return render_template('index.html',
                           categories=get_categories(),
                           latest_items=get_latest_items(),
                           session_token=get_session_token())


@app.route('/gconnect')
@google.authorized_handler
def authorized(resp):
    """
       Function to handle the auth response
       Parameter: resp
       Return render index template
    """
    access_token = resp['access_token']
    login_session['access_token'] = access_token, ''
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)
    data = answer.json()
    login_session['username'] = data['name']
    user_id = create_user(login_session['username'])
    login_session['user_id'] = user_id
    return render_template('index.html', categories=get_categories(),
                           latest_items=get_latest_items(),
                           session_token=get_session_token())


@google.tokengetter
def get_access_token(resp):
    access_token = resp['access_token']
    login_session['access_token'] = access_token, ''

    return session.get('access_token')


@app.route('/')
def categories():
    """
       Function to handle the index page
       and populate the Categories table if empty
       Return render index template
    """
    categories = get_categories()
    latest_items = get_latest_items()

    if not categories:
        categories_list = ['Soccer',
                           'Basketball',
                           'Baseball',
                           'Frisbee',
                           'Snowboarding',
                           'Rock Climbing',
                           'Foosball',
                           'Skating',
                           'Hockey']
        for category in categories_list:
            new_category = Categories(name=category)
            session.add(new_category)

        session.commit()
        categories = get_categories()

    return render_template('index.html',
                           categories=get_categories(),
                           latest_items=get_latest_items(),
                           session_token=get_session_token()
                           )


@app.route('/insert_item', methods=['GET', 'POST'])
def insert_item():
    if request.method == 'POST':
        category = session.query(Categories).\
                           filter_by(name=request.form['categories']).one()
        new_item = Items(title=request.form['title'],
                         description=request.form['description'],
                         creation_date=datetime.now(),
                         category_id=category.id,
                         user_id=login_session['user_id'])
        session.add(new_item)
        session.commit()

        return redirect(url_for('insert_item',
                                categories=get_categories(),
                                session_token=get_session_token()))

    else:
        return render_template('insert_item.html',
                               categories=get_categories(),
                               session_token=get_session_token())


@app.route('/categories/<int:category_id>/items', methods=['GET'])
def category_items(category_id):
    category_name = session.query(Categories).\
                            filter_by(id=category_id).one()
    category_items = session.query(Items)\
                            .filter_by(category_id=category_id).all()
    rows = session.query(Items).filter_by(category_id=category_id).count()

    return render_template('category_items.html',
                           category_items=category_items,
                           categories=get_categories(),
                           category_name=category_name,
                           count=rows,
                           session_token=get_session_token())


@app.route('/item/<int:item_id>', methods=['GET'])
def get_item(item_id):
    item = session.query(Items).filter_by(id=item_id).all()
    return render_template('item_description.html',
                           item=item,
                           categories=get_categories(),
                           session_token=get_session_token())


@app.route('/update_item/<int:item_id>', methods=['GET', 'POST'])
def update_item(item_id):

    if request.method == 'POST':
        edit_item = session.query(Items).filter_by(id=item_id).one()
        edit_item.id = item_id
        if request.form['title']:
            edit_item.title = request.form['title']
        if request.form['description']:
            edit_item.description = request.form['description']
        if request.form['categories']:
            category = session.query(Categories).\
                       filter_by(name=request.form['categories']).one()
            edit_item.category_id = category.id

        session.merge(edit_item)
        session.commit()
        return redirect(url_for('update_item',
                                item_id=item_id,
                                categories=get_categories(),
                                category_name=category.name,
                                session_token=get_session_token()))
    else:
        edit_item = session.query(Items).filter_by(id=item_id).one()
        category = session.query(Categories)\
                          .filter_by(id=edit_item.category_id).one()
        return render_template('update_item.html',
                               edit_item=edit_item,
                               categories=get_categories(),
                               category=category,
                               session_token=get_session_token())


@app.route('/delete_item/<int:item_id>', methods=['GET', 'POST'])
def delete_item(item_id):
    if request.method == 'POST':
        deleted_item = session.query(Items).filter_by(id=item_id).one()
        session.delete(deleted_item)
        if get_session_user_id() != deleted_item.id:
            created_by_user = False
        else:
            created_by_user = True
        session.commit()
        return redirect(url_for('delete_item',
                                deleted=str(True),
                                categories=get_categories(),
                                session_token=get_session_token(),
                                created_by_user=created_by_user,
                                item_id=1))
    else:
        deleted_item = session.query(Items).filter_by(id=item_id).all()
        return render_template('delete_item.html',
                               deleted_item=deleted_item,
                               deleted=str(False),
                               categories=get_categories(),
                               session_token=get_session_token())


@app.route('/catalog')
def catalog_JSON():
    """ Endpoint JSON  based on
    https://github.com/gmawji/item-catalog/blob/master/app.py"""

    categories = session.query(Categories).all()
    category = [c.serialize for c in categories]
    for c in range(len(category)):
        items = [i.serialize for i in session.query(Items)
                                             .filter_by(
                                             category_id=category[c]["id"]
                                             ).all()]
        if items:
            category[c]["Item"] = items

    return jsonify(Category=category)


@app.route('/catalog/<int:category_id>/<int:item_id>/JSON')
def item_catalog_JSON(category_id, item_id):

    try:
        item = session.query(Items).\
                       filter_by(id=item_id, category_id=category_id).one()
    except:
        return jsonify(None)

    return jsonify(item=item.serialize)


@app.route('/catalog/reset')
def catalog_reset():
    """
       Function to handle the tests and populate the Items table
       Return render index template
    """
    session.query(Items).delete()
    session.query(Users).delete()
    session.commit()
    user_id = create_user('ANONYMOUS')
    # Soccer
    category = session.query(Categories).filter_by(name='Soccer').one()
    new_item = Items(title='Ball',
                     description='A football is a ball in' +
                     'flated with air that is used to play one of the va' +
                     'rious sports known as football. In these games, wi' +
                     'th some exceptions, goals or points are scored onl' +
                     'y when the ball enters one of two designated goal-' +
                     'scoring areas; football games involve the two team' +
                     's each trying to move the ball in opposite directi' +
                     'ons along the field of play The first balls were m' +
                     'ade of natural materials, such as an inflated pig ' +
                     'bladder, later put inside a leather cover, which h' +
                     'as given rise to the American slang-term "pigskin"' +
                     '. Modern balls are designed by teams of engineers ' +
                     'to exacting specifications, with rubber or plastic' +
                     'bladders, and often with plastic covers. Various l' +
                     'eagues and games use different balls, though they ' +
                     'all have one of the following basic',
                     creation_date=datetime.now(),
                     category_id=category.id,
                     user_id=user_id)
    session.add(new_item)

    # Basketball
    category = session.query(Categories).filter_by(name='Basketball').one()
    new_item = Items(title='Backboard',
                     description='A backboard is a p' +
                     'iece of basketball equipment. It is a raised vert' +
                     'ical board with an attached basket consisting of ' +
                     'a net suspended from a hoop. It is made of a flat' +
                     ', rigid piece of, often Plexiglas or tempered gla' +
                     'ss which also has the properties of safety glass ' +
                     'when accidentally shattered. It is usually rectan' +
                     'gular as used in NBA, NCAA and international bask' +
                     'etball. In recreational environments, a backboard' +
                     ' may be oval or a fan-shape, particularly in non-' +
                     'professional games.',
                     creation_date=datetime.now(),
                     category_id=category.id,
                     user_id=user_id)
    session.add(new_item)

    # Baseball
    category = session.query(Categories).filter_by(name='Baseball').one()
    new_item = Items(title='Bat',
                     description='A baseball bat is a smoo' +
                     'th wooden or metal club used in the sport of base' +
                     'ball to hit the ball after it is thrown by the pi' +
                     'tcher. By regulation it may be no more than 2.75 ' +
                     'inches (70 mm) in diameter at the thickest part a' +
                     'nd no more than 42 inches (1,100 mm) long. Althou' +
                     'gh historically bats approaching 3 pounds (1.4 kg' +
                     ') were swung,[1] today bats of 33 ounces (0.94 kg' +
                     ') are common, topping out at 34 ounces (0.96 kg) ' +
                     'to 36 ounces (1.0 kg)',
                     creation_date=datetime.now(),
                     category_id=category.id,
                     user_id=user_id)
    session.add(new_item)

    # Frisbee
    category = session.query(Categories).filter_by(name='Frisbee').one()
    new_item = Items(title='Frisbee',
                     description='A frisbee (also called a flying disc' +
                     'or simply a disc)[1] is a gliding toy or sporting' +
                     ' item that is generally plastic and roughly 20 to' +
                     ' 25 centimetres (8 to 10 in) in diameter with a l' +
                     'ip,[2] used recreationally and competitively for ' +
                     'throwing and catching, for example, in flying dis' +
                     'c games. The shape of the disc, an airfoil in cro' +
                     'ss-section, allows it to fly by generating lift a' +
                     's it moves through the air while spinning.',
                     creation_date=datetime.now(),
                     category_id=category.id,
                     user_id=user_id)
    session.add(new_item)

    # Snowboarding
    category = session.query(Categories).filter_by(name='Snowboarding').one()
    new_item = Items(title='Snowboards',
                     description='Snowboards are boards where both fee' +
                     't are secured to the same board, which are wider ' +
                     'than skis, with the ability to glide on snow.[1] ' +
                     'Snowboards widths are between 6 and 12 inches or ' +
                     '15 to 30 centimeters.[2] Snowboards are different' +
                     'iated from monoskis by the stance of the user',
                     creation_date=datetime.now(),
                     category_id=category.id,
                     user_id=user_id)
    session.add(new_item)

    # Rock Climbing
    category = session.query(Categories).filter_by(name='Rock Climbing').one()
    new_item = Items(title='Rope',
                     description='Climbing ropes are typically of kern' +
                     'mantle construction, consisting of a core (kern) ' +
                     'of long twisted fibres and an outer sheath (mantl' +
                     'e) of woven coloured fibres. The core provides ab' +
                     'out 80% of the tensile strength, while the sheath' +
                     ' is a durable layer that protects the core and gi' +
                     'ves the rope desirable handling characteristics.',
                     creation_date=datetime.now(),
                     category_id=category.id,
                     user_id=user_id)
    session.add(new_item)

    # Foosball

    # Skating
    category = session.query(Categories).filter_by(name='Skating').one()
    new_item = Items(title='Inline Skates',
                     description='Inline skates are a type of roller s' +
                     'kate used for inline skating. Unlike quad skates,' +
                     ' which have two front and two rear wheels, inline' +
                     ' skates typically have two to five wheels arrange' +
                     'd in a single line. Some, especially those for re' +
                     'creation, have a rubber "stop" or "brake" block a' +
                     'ttached to the rear of one or occasionally both o' +
                     'f the skates so that the skater can slow down or ' +
                     'stop by leaning back on the foot with the brake skate.',
                     creation_date=datetime.now(),
                     category_id=category.id,
                     user_id=user_id)
    session.add(new_item)

    # Hockey
    category = session.query(Categories).filter_by(name='Hockey').one()
    new_item = Items(title='Stick',
                     description='A hockey stick is a piece of sport eq' +
                     'uipment used by the players in all the forms of ho' +
                     'ckey to move the ball or puck (as appropriate to t' +
                     'he type of hockey) either to push, pull, hit, stri' +
                     'ke, flick, steer, launch or stop the ball/puck dur' +
                     'ing play with the objective being to move the ball' +
                     '/puck around the playing area and between team mem' +
                     'bers using the stick, and to ultimately score a go' +
                     'al with it against an opposing team.',
                     creation_date=datetime.now(),
                     category_id=category.id,
                     user_id=user_id)
    session.add(new_item)

    session.commit()

    return render_template('index.html',
                           categories=get_categories(),
                           latest_items=get_latest_items())


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
