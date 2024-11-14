from urllib.parse import urlsplit
from flask import render_template, flash, redirect, url_for, request, current_app, send_from_directory
from flask_login import login_user, logout_user, current_user, login_required
import sqlalchemy as sa
from app import app, db
from app.forms import LoginForm, RegistrationForm, EditProfileForm, EmptyForm, PostForm
from app.models import User, Post, Chat, Message
from datetime import datetime, timezone
from sqlalchemy import desc, func, or_
import os
from werkzeug.utils import secure_filename


@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(body=form.post.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Your post is now live!')
        return redirect(url_for('index'))
    page = request.args.get('page', 1, type=int)
    posts = db.paginate(current_user.following_posts(), page=page,
                        per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('index', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('index', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('index.html', title='Home', form=form,
                           posts=posts.items, next_url=next_url,
                           prev_url=prev_url)


@app.route('/explore')
@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    query = sa.select(Post).order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=app.config['POSTS_PER_PAGE'], error_out=False)

    current_user.last_seen_post = datetime.now(timezone.utc)
    db.session.commit()

    next_url = url_for('explore', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('explore', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('index.html', title='Explore', posts=posts.items,
                           next_url=next_url, prev_url=prev_url)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route('/user/<username>')
@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    page = request.args.get('page', 1, type=int)
    query = user.posts.select().order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=app.config['POSTS_PER_PAGE'],
                        error_out=False)
    next_url = url_for('user', username=user.username, page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('user', username=user.username, page=posts.prev_num) \
        if posts.has_prev else None
    form = EmptyForm()

    unread_chats = db.session.query(Chat).join(Message).filter(
        Message.read == False,
        Message.sender_id != current_user.id,
        (Chat.user1_id == current_user.id) | (Chat.user2_id == current_user.id)
    ).group_by(Chat.id).all()

    return render_template('user.html', user=user, posts=posts.items,
                           next_url=next_url, prev_url=prev_url, form=form, unread_chats=unread_chats)


@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data

        if form.avatar.data:
            filename = secure_filename(form.avatar.data.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            form.avatar.data.save(file_path)
            current_user.avatar_filename = filename

        if form.password.data:
            current_user.set_password(form.password.data)

        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile', form=form)


@app.route('/uploads/<filename>')
def uploads(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username))
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('index'))
        if user == current_user:
            flash('You cannot follow yourself!')
            return redirect(url_for('user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash(f'You are following {username}!')
        return redirect(url_for('user', username=username))
    else:
        return redirect(url_for('index'))


@app.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username))
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('index'))
        if user == current_user:
            flash('You cannot unfollow yourself!')
            return redirect(url_for('user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(f'You are not following {username}.')
        return redirect(url_for('user', username=username))
    else:
        return redirect(url_for('index'))


@app.route('/start_chat/<int:user_id>', methods=['GET', 'POST'])
@login_required
def start_chat(user_id):
    chat = Chat.query.filter_by(user1_id=current_user.id, user2_id=user_id).first() or \
           Chat.query.filter_by(user1_id=user_id, user2_id=current_user.id).first()
    if not chat:
        chat = Chat(user1_id=current_user.id, user2_id=user_id)
        db.session.add(chat)
        db.session.commit()
    return redirect(url_for('chat', chat_id=chat.id))


@app.route('/chat/<int:chat_id>', methods=['GET', 'POST'])
@login_required
def chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    if current_user.id in [chat.user1_id, chat.user2_id]:
        if chat.user1_id == current_user.id:
            other_user = User.query.get(chat.user2_id)
        else:
            other_user = User.query.get(chat.user1_id)

        Message.query.filter_by(chat_id=chat.id, read=False).filter(Message.sender_id != current_user.id).update(
            {"read": True})
        db.session.commit()

        if request.method == 'POST':
            message = Message(chat_id=chat.id, sender_id=current_user.id, content=request.form['message'])
            message.read = False
            db.session.add(message)
            db.session.commit()

        page = request.args.get('page', 1, type=int)
        messages = Message.query.filter_by(chat_id=chat.id).order_by(Message.timestamp.desc()).paginate \
            (page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)

        next_url = url_for('chat', chat_id=chat.id, page=messages.next_num) if messages.has_next else None
        prev_url = url_for('chat', chat_id=chat.id, page=messages.prev_num) if messages.has_prev else None

        return render_template('chat.html', chat=chat, messages=messages.items, \
                               other_user=other_user, next_url=next_url, prev_url=prev_url)


@app.route('/chats')
@login_required
def chats():
    search_query = request.args.get('search_query', '').strip()

    latest_messages = db.session.query(
        Message.chat_id, func.max(Message.timestamp).label('last_msg_time')
    ).group_by(Message.chat_id).subquery()

    user_chats = db.session.query(Chat).join(
        latest_messages, Chat.id == latest_messages.c.chat_id
    ).filter(
        (Chat.user1_id == current_user.id) | (Chat.user2_id == current_user.id)
    ).order_by(desc(latest_messages.c.last_msg_time))

    if search_query:
        user_chats = user_chats.join(User, or_(
            Chat.user1_id == User.id, Chat.user2_id == User.id
        )).filter(User.username.ilike(f"%{search_query}%"))

    chat_data = [
        {
            "chat": chat,
            "other_user": User.query.get(chat.user1_id) if chat.user2_id == current_user.id else \
                User.query.get(chat.user2_id),
            "unread_count": Message.query.filter_by(chat_id=chat.id, read=False).filter(
                Message.sender_id != current_user.id).count()
        }
        for chat in user_chats.all()
    ]

    return render_template('chats.html', chats=chat_data)
