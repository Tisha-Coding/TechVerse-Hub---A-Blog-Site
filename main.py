from flask import Flask, render_template, request, session, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename
import json
import os
import math
from flask_mail import Mail

# Load configuration from the JSON file
local_server = True
with open('config.json', 'r') as c:
    params = json.load(c)["params"]

# Initialize the Flask application
app = Flask(__name__)
app.secret_key = 'super-secret-key'
app.config['UPLOAD_FOLDER'] = params['upload_location']

# Flask-Mail configuration
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT='465',
    MAIL_USE_SSL=True,
    MAIL_USERNAME=params['gmail-user'],
    MAIL_PASSWORD=params['gmail-password']
)
mail = Mail(app)

# Configure the SQLAlchemy connection string
if local_server:
    app.config["SQLALCHEMY_DATABASE_URI"] = params['local_uri']
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = params['prod_uri']

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# Define the Contacts model
class Contacts(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=False, nullable=False)
    phone_num = db.Column(db.String(120), nullable=False)
    msg = db.Column(db.String(120), nullable=False)
    date = db.Column(db.DateTime, nullable=True)
    email = db.Column(db.String(120), nullable=True)


# Define the Posts model
class Posts(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(120), nullable=False)
    content = db.Column(db.String(120), nullable=False)
    date = db.Column(db.DateTime, nullable=True)
    img_file = db.Column(db.String(12), nullable=True)
    tagline = db.Column(db.String(120), nullable=False)


# Route for the home page
@app.route("/")
def home():
    # Retrieve all posts
    posts = Posts.query.filter_by().all()
    last = math.ceil(len(posts) / int(params['no_of_posts']))

    # Get the 'page' parameter from the query string
    page = request.args.get('page')

    # Set default value for 'page' if it's not provided or not numeric
    if page is None or not page.isnumeric():
        page = 1
    else:
        page = int(page)

    # Pagination logic
    posts = posts[(page - 1) * int(params['no_of_posts']): (page - 1) * int(params['no_of_posts']) + int(
        params['no_of_posts'])]

    if page == 1:
        prev = '#'
        next = f"/?page={page + 1}"
    elif page == last:
        prev = f"/?page={page - 1}"
        next = '#'
    else:
        prev = f"/?page={page - 1}"
        next = f"/?page={page + 1}"

    return render_template('index.html', params=params, posts=posts, prev=prev, next=next)


# Route for the about page
@app.route("/about")
def about():
    return render_template('about.html', params=params)


# Route for the contact page
@app.route("/contact", methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Get data from form
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        message = request.form.get('message')

        # Create a new contact entry
        entry = Contacts(name=name, phone_num=phone, msg=message, date=datetime.now(), email=email)

        # Add entry to the database
        db.session.add(entry)
        db.session.commit()
        mail.send_message('New Message From Blog', sender=email, recipients=[params['gmail-user']],
                          body=message + "\n" + phone)
        flash("Thanks for submitting your details. We will get back to you soon", "success")
    return render_template('contact.html', params=params)


# Route for viewing a post
@app.route("/post/<string:post_slug>", methods=['GET'])
def post(post_slug):
    post = Posts.query.filter_by(slug=post_slug).first()
    return render_template('post.html', params=params, post=post)


# Route for the dashboard
@app.route("/dashboard", methods=['GET', 'POST'])
def dashboard():
    if 'user' in session and session['user'] == params['admin_user']:
        posts = Posts.query.all()
        return render_template('dashboard.html', params=params, posts=posts)

    if request.method == 'POST':
        username = request.form.get('uname')
        userpass = request.form.get('pass')
        if username == params['admin_user'] and userpass == params['admin_password']:
            session['user'] = username
            posts = Posts.query.all()
            return render_template('dashboard.html', params=params, posts=posts)

    return render_template('login.html', params=params)


# Route for editing or adding a post
@app.route("/edit/<string:sno>", methods=['GET', 'POST'])
def edit(sno):
    if 'user' in session and session['user'] == params['admin_user']:
        if request.method == 'POST':
            box_title = request.form.get('title')
            tline = request.form.get('tline')
            slug = request.form.get('slug')
            content = request.form.get('content')
            img_file = request.form.get('img_file')

            if sno == '0':
                # Create a new post with the current date
                post = Posts(title=box_title, slug=slug, content=content, tagline=tline, img_file=img_file,
                             date=datetime.now())
                db.session.add(post)
                db.session.commit()
                flash("New Post has been added successfully", "success")

            else:
                # Update the existing post
                post = Posts.query.filter_by(sno=sno).first()
                post.title = box_title
                post.slug = slug
                post.content = content
                post.tagline = tline
                post.img_file = img_file
                db.session.commit()
                flash("Post has been updated successfully", "success")

        post = Posts.query.filter_by(sno=sno).first()
        return render_template('edit.html', params=params, post=post)

    return redirect('/dashboard')


# Route for deleting a post
@app.route("/delete/<string:sno>")
def delete(sno):
    if 'user' in session and session['user'] == params['admin_user']:
        post = Posts.query.filter_by(sno=sno).first()
        if post:
            db.session.delete(post)
            db.session.commit()
            flash("Post has been deleted successfully", "success")

    return redirect('/dashboard')


# Route for uploading files
@app.route("/uploader", methods=['POST'])
def uploader():
    if 'user' in session and session['user'] == params['admin_user']:
        if 'file1' in request.files:
            file = request.files['file1']
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            flash("File has been uploaded successfully", "success")

    return redirect('/dashboard')


# Route for logging out
@app.route("/logout")
def logout():
    session.pop('user', None)
    return redirect('/dashboard')


# Run the Flask application
if __name__ == "__main__":
    app.run(debug=True)
