# tests/test_checklists.py
import pytest
from flask import url_for, session
from app.app import Checklist, ChecklistItem, User, db # Ensure your app structure allows this import

@pytest.fixture
def checklist_user_client(client, create_test_user, init_database): # Renamed & added init_database
    user = create_test_user(email='checklist_user@example.com', name='Checklist User')
    with client.session_transaction() as http_session:
        http_session['_user_id'] = str(user.id)
        http_session['_fresh'] = True
    return client, user

def test_create_checklist(checklist_user_client, init_database): # Added init_database
    client, user = checklist_user_client
    response = client.post(url_for('new_checklist'), data={'title': 'My Test Checklist'}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Checklist created successfully!" in response.data
    
    # Verify in database
    checklist = Checklist.query.filter_by(title='My Test Checklist').first()
    assert checklist is not None
    assert checklist.user_id == user.id

def test_view_checklist_and_items(checklist_user_client, init_database): # Added init_database
    client, user = checklist_user_client
    # Create a checklist
    client.post(url_for('new_checklist'), data={'title': 'Shopping List'})
    cl = Checklist.query.filter_by(user_id=user.id, title='Shopping List').first()
    assert cl is not None
    cl_id = cl.id
    
    # Add items to the checklist
    client.post(url_for('add_checklist_item', checklist_id=cl_id), data={'text': 'Milk'})
    client.post(url_for('add_checklist_item', checklist_id=cl_id), data={'text': 'Bread'})

    response = client.get(url_for('view_checklist', checklist_id=cl_id))
    assert response.status_code == 200
    assert b"Shopping List" in response.data
    assert b"Milk" in response.data
    assert b"Bread" in response.data
    
    # Verify items in database
    items = ChecklistItem.query.filter_by(checklist_id=cl_id).all()
    assert len(items) == 2
    item_texts = {item.text for item in items}
    assert "Milk" in item_texts
    assert "Bread" in item_texts

def test_edit_checklist_title(checklist_user_client, init_database):
    client, user = checklist_user_client
    client.post(url_for('new_checklist'), data={'title': 'Original Checklist Title'})
    cl = Checklist.query.filter_by(user_id=user.id, title='Original Checklist Title').first()
    assert cl is not None
    cl_id = cl.id

    response = client.post(url_for('edit_checklist', checklist_id=cl_id), data={'title': 'Updated Checklist Title'}, follow_redirects=True)
    assert response.status_code == 200 # Should redirect to view_checklist
    assert b"Checklist updated successfully!" in response.data
    assert b"Updated Checklist Title" in response.data # Check if new title is on view page

    updated_cl = Checklist.query.get(cl_id)
    assert updated_cl.title == 'Updated Checklist Title'


def test_delete_checklist(checklist_user_client, init_database):
    client, user = checklist_user_client
    client.post(url_for('new_checklist'), data={'title': 'Checklist To Delete'})
    cl = Checklist.query.filter_by(user_id=user.id, title='Checklist To Delete').first()
    assert cl is not None
    cl_id = cl.id
    
    # Add an item to ensure cascade delete is tested (if configured)
    client.post(url_for('add_checklist_item', checklist_id=cl_id), data={'text': 'Item in doomed checklist'})
    assert ChecklistItem.query.filter_by(checklist_id=cl_id).count() == 1

    response = client.post(url_for('delete_checklist', checklist_id=cl_id), follow_redirects=True)
    assert response.status_code == 200
    assert b"Checklist deleted successfully!" in response.data
    assert Checklist.query.get(cl_id) is None
    assert ChecklistItem.query.filter_by(checklist_id=cl_id).count() == 0 # Check cascade delete

def test_toggle_checklist_item(checklist_user_client, init_database): # Added init_database
    client, user = checklist_user_client
    client.post(url_for('new_checklist'), data={'title': 'Tasks'})
    cl = Checklist.query.filter_by(user_id=user.id, title='Tasks').first()
    cl_id = cl.id
    
    client.post(url_for('add_checklist_item', checklist_id=cl_id), data={'text': 'Task 1'})
    item = ChecklistItem.query.filter_by(checklist_id=cl_id, text='Task 1').first()
    item_id = item.id

    assert not item.completed # Initially false

    res_toggle1 = client.post(url_for('toggle_checklist_item', item_id=item_id), follow_redirects=True)
    assert res_toggle1.status_code == 200
    assert b"Item status updated!" in res_toggle1.data
    item = ChecklistItem.query.get(item_id) # Re-fetch from DB
    assert item.completed # Should be true after toggle

    res_toggle2 = client.post(url_for('toggle_checklist_item', item_id=item_id), follow_redirects=True)
    assert res_toggle2.status_code == 200
    assert b"Item status updated!" in res_toggle2.data
    item = ChecklistItem.query.get(item_id) # Re-fetch
    assert not item.completed # Should be false after second toggle

def test_delete_checklist_item(checklist_user_client, init_database):
    client, user = checklist_user_client
    client.post(url_for('new_checklist'), data={'title': 'List With Item To Delete'})
    cl = Checklist.query.filter_by(user_id=user.id, title='List With Item To Delete').first()
    cl_id = cl.id
    
    client.post(url_for('add_checklist_item', checklist_id=cl_id), data={'text': 'Ephemeral Item'})
    item = ChecklistItem.query.filter_by(checklist_id=cl_id, text='Ephemeral Item').first()
    item_id = item.id
    assert ChecklistItem.query.get(item_id) is not None

    response = client.post(url_for('delete_checklist_item', item_id=item_id), follow_redirects=True)
    assert response.status_code == 200
    assert b"Item deleted successfully!" in response.data
    assert ChecklistItem.query.get(item_id) is None

def test_checklist_ownership(checklist_user_client, create_test_user, init_database):
    client, user1 = checklist_user_client # User 1 is logged in

    # User 1 creates a checklist
    client.post(url_for('new_checklist'), data={'title': 'User1 Checklist'})
    cl1 = Checklist.query.filter_by(user_id=user1.id, title='User1 Checklist').first()
    cl1_id = cl1.id
    client.post(url_for('add_checklist_item', checklist_id=cl1_id), data={'text': 'User1 Item'})
    item1_id = ChecklistItem.query.filter_by(checklist_id=cl1_id).first().id


    # Create User 2 (not logged in with this client)
    user2 = create_test_user(email='user2@example.com', name='User Two')
    with client.application.app_context(): # Use app_context for DB operations outside of request
        cl2 = Checklist(title='User2 Checklist', user_id=user2.id)
        db.session.add(cl2)
        db.session.commit()
        cl2_id = cl2.id
        item2 = ChecklistItem(text='User2 Item', checklist_id=cl2_id)
        db.session.add(item2)
        db.session.commit()
        item2_id = item2.id

    # User 1 tries to view User 2's checklist
    response_view = client.get(url_for('view_checklist', checklist_id=cl2_id))
    assert b"You are not authorized to view this checklist." in response_view.data

    # User 1 tries to edit User 2's checklist title (GET and POST)
    response_edit_get = client.get(url_for('edit_checklist', checklist_id=cl2_id))
    assert b"You are not authorized to edit this checklist." in response_edit_get.data
    response_edit_post = client.post(url_for('edit_checklist', checklist_id=cl2_id), data={'title': 'Hacked Title'}, follow_redirects=True)
    assert b"You are not authorized to edit this checklist." in response_edit_post.data
    
    # User 1 tries to delete User 2's checklist
    response_delete_cl = client.post(url_for('delete_checklist', checklist_id=cl2_id), follow_redirects=True)
    assert b"You are not authorized to delete this checklist." in response_delete_cl.data

    # User 1 tries to add item to User 2's checklist
    response_add_item = client.post(url_for('add_checklist_item', checklist_id=cl2_id), data={'text': 'Intruder Item'}, follow_redirects=True)
    assert b"You are not authorized to add items to this checklist." in response_add_item.data
    
    # User 1 tries to toggle User 2's item
    response_toggle_item = client.post(url_for('toggle_checklist_item', item_id=item2_id), follow_redirects=True)
    assert b"You are not authorized to modify this item." in response_toggle_item.data

    # User 1 tries to delete User 2's item
    response_delete_item = client.post(url_for('delete_checklist_item', item_id=item2_id), follow_redirects=True)
    assert b"You are not authorized to delete this item." in response_delete_item.data

    # Ensure User 2's checklist and item are unchanged
    assert Checklist.query.get(cl2_id).title == 'User2 Checklist'
    assert ChecklistItem.query.get(item2_id).text == 'User2 Item'
    assert not ChecklistItem.query.get(item2_id).completed
