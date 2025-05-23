# tests/test_notes.py
import pytest
from flask import url_for, session
from app.app import Note, User, db # Assuming Note model can be imported

@pytest.fixture
def logged_in_client(client, create_test_user, init_database): # Added init_database
    user = create_test_user(email='notes_user@example.com', name='Notes User')
    with client.session_transaction() as http_session:
        http_session['_user_id'] = str(user.id) # Flask-Login typically uses '_user_id'
        http_session['_fresh'] = True
        # If you use user_id directly in session for login:
        # http_session['user_id'] = user.id 
    return client, user # Return both client and user object

def test_create_note(logged_in_client, init_database): # Added init_database
    client, user = logged_in_client
    response = client.post(url_for('new_note'), data={
        'title': 'Test Note Title',
        'content': 'Test Note Content'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Note created successfully!" in response.data
    
    # Verify in database
    note = Note.query.filter_by(title='Test Note Title').first()
    assert note is not None
    assert note.content == 'Test Note Content'
    assert note.user_id == user.id

def test_view_notes(logged_in_client, create_test_user, init_database): # Added init_database and create_test_user
    client, user = logged_in_client
    # Create a note for this user
    client.post(url_for('new_note'), data={'title': 'My Note', 'content': 'Content'})
    
    # Create another user and their note
    other_user = create_test_user(email='other@example.com', name='Other User')
    # Manually create note for other_user as we don't have their client logged in
    with client.application.app_context(): # Ensure app context for db operations
        other_note = Note(title='Other Note', content='Other Content', user_id=other_user.id)
        db.session.add(other_note)
        db.session.commit()

    response = client.get(url_for('notes'))
    assert response.status_code == 200
    assert b"My Note" in response.data
    assert b"Other Note" not in response.data # Should not see other user's notes

def test_edit_note(logged_in_client, init_database): # Added init_database
    client, user = logged_in_client
    # Create a note
    client.post(url_for('new_note'), data={'title': 'Original Title', 'content': 'Original Content'})
    
    # Fetch the created note's ID
    note_id = Note.query.filter_by(user_id=user.id, title='Original Title').first().id

    response = client.post(url_for('edit_note', note_id=note_id), data={
        'title': 'Updated Title',
        'content': 'Updated Content'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Note updated successfully!" in response.data
    
    updated_note = Note.query.get(note_id)
    assert updated_note.title == 'Updated Title'
    assert updated_note.content == 'Updated Content'

def test_delete_note(logged_in_client, init_database): # Added init_database
    client, user = logged_in_client
    client.post(url_for('new_note'), data={'title': 'To Delete', 'content': 'Content'})
    note_id = Note.query.filter_by(user_id=user.id, title='To Delete').first().id
    
    response = client.post(url_for('delete_note', note_id=note_id), follow_redirects=True)
    assert response.status_code == 200
    assert b"Note deleted successfully!" in response.data
    assert Note.query.get(note_id) is None

def test_edit_another_users_note_forbidden(logged_in_client, create_test_user, init_database):
    client, current_user_obj = logged_in_client # This is user 1
    
    # Create another user and their note
    other_user = create_test_user(email='other_user@example.com', name='Other User')
    with client.application.app_context():
        other_note = Note(title="Other's Note", content="Secret content", user_id=other_user.id)
        db.session.add(other_note)
        db.session.commit()
        other_note_id = other_note.id

    # Current user tries to edit other_user's note
    response = client.post(url_for('edit_note', note_id=other_note_id), data={
        'title': 'Attempted Hack',
        'content': 'Malicious Content'
    }, follow_redirects=True)
    
    assert response.status_code == 200 # Should redirect to notes page
    assert b"You are not authorized to edit this note." in response.data
    
    # Verify the note was not changed
    original_note = Note.query.get(other_note_id)
    assert original_note.title == "Other's Note"
    assert original_note.content == "Secret content"

def test_delete_another_users_note_forbidden(logged_in_client, create_test_user, init_database):
    client, current_user_obj = logged_in_client

    other_user = create_test_user(email='victim_user@example.com', name='Victim User')
    with client.application.app_context():
        other_note = Note(title="Victim's Note", content="Fragile data", user_id=other_user.id)
        db.session.add(other_note)
        db.session.commit()
        other_note_id = other_note.id

    response = client.post(url_for('delete_note', note_id=other_note_id), follow_redirects=True)
    
    assert response.status_code == 200
    assert b"You are not authorized to delete this note." in response.data
    assert Note.query.get(other_note_id) is not None # Note should still exist
