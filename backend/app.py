from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
import sqlite3
import os
import yt_dlp
import requests
from bs4 import BeautifulSoup
import re
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['DOWNLOAD_FOLDER'] = 'static/downloads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

def init_db():
    conn = sqlite3.connect('blog.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS blog_posts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT NOT NULL,
                  content TEXT NOT NULL,
                  author TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS contact_messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  email TEXT NOT NULL,
                  subject TEXT NOT NULL,
                  message TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS download_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  platform TEXT NOT NULL,
                  url TEXT NOT NULL,
                  filename TEXT NOT NULL,
                  status TEXT DEFAULT 'completed',
                  downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        password_hash = generate_password_hash('admin123')
        c.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                  ('admin', 'admin@example.com', password_hash))
        print("Admin user created: username='admin', password='admin123'")
    
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect('blog.db')
    conn.row_factory = sqlite3.Row
    return conn

def download_youtube_video(url, quality='best'):
    try:
        ydl_opts = {
            'outtmpl': os.path.join(app.config['DOWNLOAD_FOLDER'], '%(title)s.%(ext)s'),
            'format': quality,
        }
        
        if os.path.exists('cookies.txt'):
            ydl_opts['cookiefile'] = 'cookies.txt'
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return filename, info.get('title', 'YouTube Video')
    
    except Exception as e:
        raise Exception(f"YouTube download error: {str(e)}")

def download_instagram_video(url):
    try:
        ydl_opts = {
            'outtmpl': os.path.join(app.config['DOWNLOAD_FOLDER'], 'instagram_%(title)s.%(ext)s'),
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return filename, info.get('title', 'Instagram Video')
    
    except Exception as e:
        raise Exception(f"Instagram download error: {str(e)}")

def download_pinterest_video(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        video_sources = []
        video_tags = soup.find_all('video')
        for video in video_tags:
            if video.get('src'):
                video_sources.append(video['src'])
            source_tags = video.find_all('source')
            for source in source_tags:
                if source.get('src'):
                    video_sources.append(source['src'])
        
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                video_urls = re.findall(r'https?://[^"\']*\.mp4[^"\']*', script.string)
                video_sources.extend(video_urls)
        
        for video_url in video_sources:
            try:
                if 'pinimg.com' in video_url or 'pinterest.com' in video_url:
                    video_response = requests.get(video_url, headers=headers)
                    if video_response.status_code == 200:
                        filename = f"pinterest_video_{uuid.uuid4().hex[:8]}.mp4"
                        filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
                        
                        with open(filepath, 'wb') as f:
                            f.write(video_response.content)
                        
                        return filepath, "Pinterest Video"
            except:
                continue
        
        raise Exception("Could not find downloadable video")
    
    except Exception as e:
        raise Exception(f"Pinterest download error: {str(e)}")

def detect_platform(url):
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    elif 'instagram.com' in url:
        return 'instagram'
    elif 'pinterest.com' in url or 'pin.it' in url:
        return 'pinterest'
    else:
        return 'unknown'

@app.route('/')
def index():
    conn = get_db_connection()
    posts = conn.execute('SELECT * FROM blog_posts ORDER BY created_at DESC LIMIT 3').fetchall()
    conn.close()
    return render_template('index.html', posts=posts)

@app.route('/downloader')
def downloader():
    return render_template('downloader.html')

@app.route('/download', methods=['POST'])
def download_video():
    try:
        url = request.form['url']
        quality = request.form.get('quality', 'best')
        
        if not url:
            flash('Please enter a valid URL', 'error')
            return redirect(url_for('downloader'))
        
        platform = detect_platform(url)
        
        if platform == 'unknown':
            flash('Unsupported platform. Please use YouTube, Instagram, or Pinterest.', 'error')
            return redirect(url_for('downloader'))
        
        if platform == 'youtube':
            filename, title = download_youtube_video(url, quality)
        elif platform == 'instagram':
            filename, title = download_instagram_video(url)
        elif platform == 'pinterest':
            filename, title = download_pinterest_video(url)
        
        if 'user_id' in session:
            conn = get_db_connection()
            conn.execute('INSERT INTO download_history (user_id, platform, url, filename) VALUES (?, ?, ?, ?)',
                         (session['user_id'], platform, url, os.path.basename(filename)))
            conn.commit()
            conn.close()
        
        flash(f'Video "{title}" downloaded successfully!', 'success')
        return send_file(filename, as_attachment=True)
        
    except Exception as e:
        flash(f'Download failed: {str(e)}', 'error')
        return redirect(url_for('downloader'))

@app.route('/get_video_info', methods=['POST'])
def get_video_info():
    try:
        url = request.json.get('url')
        if not url:
            return jsonify({'error': 'No URL provided'}), 400
        
        platform = detect_platform(url)
        
        if platform == 'youtube':
            ydl_opts = {'quiet': True}
            if os.path.exists('cookies.txt'):
                ydl_opts['cookiefile'] = 'cookies.txt'
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return jsonify({
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'platform': platform
                })
        
        return jsonify({'platform': platform, 'title': 'Video'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/blog')
def blog():
    conn = get_db_connection()
    posts = conn.execute('SELECT * FROM blog_posts ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('blogs.html', posts=posts)

@app.route('/blog/<int:post_id>')
def blog_post(post_id):
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM blog_posts WHERE id = ?', (post_id,)).fetchone()
    conn.close()
    
    if post is None:
        flash('Post not found!', 'error')
        return redirect(url_for('blog'))
    
    return render_template('blog_post.html', post=post)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        subject = request.form['subject']
        message = request.form['message']
        
        conn = get_db_connection()
        conn.execute('INSERT INTO contact_messages (name, email, subject, message) VALUES (?, ?, ?, ?)',
                     (name, email, subject, message))
        conn.commit()
        conn.close()
        
        flash('Your message has been sent successfully!', 'success')
        return redirect(url_for('contact'))
    
    return render_template('contact.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('admin'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    posts = conn.execute('SELECT * FROM blog_posts ORDER BY created_at DESC').fetchall()
    messages = conn.execute('SELECT * FROM contact_messages ORDER BY created_at DESC LIMIT 10').fetchall()
    downloads = conn.execute('''SELECT dh.*, u.username 
                              FROM download_history dh 
                              LEFT JOIN users u ON dh.user_id = u.id 
                              ORDER BY dh.downloaded_at DESC LIMIT 20''').fetchall()
    
    total_downloads = conn.execute('SELECT COUNT(*) FROM download_history').fetchone()[0]
    youtube_downloads = conn.execute('SELECT COUNT(*) FROM download_history WHERE platform = "youtube"').fetchone()[0]
    instagram_downloads = conn.execute('SELECT COUNT(*) FROM download_history WHERE platform = "instagram"').fetchone()[0]
    pinterest_downloads = conn.execute('SELECT COUNT(*) FROM download_history WHERE platform = "pinterest"').fetchone()[0]
    
    conn.close()
    
    return render_template('admin.html', 
                         posts=posts, 
                         messages=messages, 
                         downloads=downloads,
                         total_downloads=total_downloads,
                         youtube_downloads=youtube_downloads,
                         instagram_downloads=instagram_downloads,
                         pinterest_downloads=pinterest_downloads)

@app.route('/admin/create-post', methods=['GET', 'POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        author = session['username']
        
        conn = get_db_connection()
        conn.execute('INSERT INTO blog_posts (title, content, author) VALUES (?, ?, ?)',
                     (title, content, author))
        conn.commit()
        conn.close()
        
        flash('Blog post created successfully!', 'success')
        return redirect(url_for('admin'))
    
    return render_template('create_post.html')

@app.route('/admin/edit-post/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        conn.execute('UPDATE blog_posts SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                     (title, content, post_id))
        conn.commit()
        conn.close()
        
        flash('Blog post updated successfully!', 'success')
        return redirect(url_for('admin'))
    
    post = conn.execute('SELECT * FROM blog_posts WHERE id = ?', (post_id,)).fetchone()
    conn.close()
    
    if post is None:
        flash('Post not found!', 'error')
        return redirect(url_for('admin'))
    
    return render_template('edit_post.html', post=post)

@app.route('/admin/delete-post/<int:post_id>')
def delete_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    conn.execute('DELETE FROM blog_posts WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()
    
    flash('Blog post deleted successfully!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/delete-message/<int:message_id>')
def delete_message(message_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    conn.execute('DELETE FROM contact_messages WHERE id = ?', (message_id,))
    conn.commit()
    conn.close()
    
    flash('Message deleted successfully!', 'success')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)
