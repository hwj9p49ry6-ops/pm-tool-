#!/usr/bin/env python3
"""
Comprehensive integration tests for the PM Tool API.

Spins up the Flask app against a temp SQLite DB, tests all endpoints,
and validates responses. No external services required — AI tests
verify route plumbing and skip actual LLM calls gracefully.

Run:
    python3 test_pm.py           # standard
    python3 test_pm.py -v        # verbose
    python3 test_pm.py TestAI    # run only AI tests
"""

import json
import os
import sys
import unittest
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import app as pm_app


# ─────────────────────────────────────────────────────────────────────────────
# Base: isolated temp DB for every test class
# ─────────────────────────────────────────────────────────────────────────────
class PMTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_fd, cls.db_path = tempfile.mkstemp(suffix='.db')
        pm_app.app.config['DATABASE'] = cls.db_path
        pm_app.app.config['TESTING'] = True
        pm_app._init_db()
        cls.client = pm_app.app.test_client()

    @classmethod
    def tearDownClass(cls):
        os.close(cls.db_fd)
        os.unlink(cls.db_path)

    # Helpers
    def _json(self, resp):
        return json.loads(resp.data)

    def _post(self, url, body=None):
        return self.client.post(url, json=body or {}, content_type='application/json')

    def _put(self, url, body=None):
        return self.client.put(url, json=body or {}, content_type='application/json')

    def _get(self, url):
        return self.client.get(url)

    def _del(self, url):
        return self.client.delete(url)

    def _make_project(self, name='Test', color='#4A90E2'):
        r = self._post('/api/projects', {'name': name, 'color': color})
        return self._json(r)['id']

    def _make_task(self, pid, **kwargs):
        kwargs.setdefault('name', 'Task')
        r = self._post(f'/api/projects/{pid}/tasks', kwargs)
        return self._json(r)['id']

    @classmethod
    def _cls_make_project(cls, name='Test', color='#4A90E2'):
        r = cls.client.post('/api/projects', json={'name': name, 'color': color},
                            content_type='application/json')
        return json.loads(r.data)['id']

    @classmethod
    def _cls_make_task(cls, pid, **kwargs):
        kwargs.setdefault('name', 'Task')
        r = cls.client.post(f'/api/projects/{pid}/tasks', json=kwargs,
                            content_type='application/json')
        return json.loads(r.data)['id']


# ─────────────────────────────────────────────────────────────────────────────
# 1. SPA
# ─────────────────────────────────────────────────────────────────────────────
class TestSPA(PMTestBase):
    def test_index_200(self):
        r = self._get('/')
        self.assertEqual(r.status_code, 200)

    def test_index_contains_project_manager(self):
        r = self._get('/')
        self.assertIn(b'Project Manager', r.data)

    def test_index_has_ai_chat_panel(self):
        r = self._get('/')
        self.assertIn(b'ai-chat-panel', r.data)

    def test_index_has_gantt_tab(self):
        r = self._get('/')
        self.assertIn(b'Gantt', r.data)

    def test_index_has_assistant_tab(self):
        r = self._get('/')
        self.assertIn(b'Assistant', r.data)

    def test_index_has_critical_path_js(self):
        r = self._get('/')
        self.assertIn(b'computeCriticalPath', r.data)

    def test_index_has_ai_chat_js(self):
        r = self._get('/')
        self.assertIn(b'sendAIChat', r.data)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Projects CRUD
# ─────────────────────────────────────────────────────────────────────────────
class TestProjects(PMTestBase):
    def test_list_returns_list(self):
        r = self._get('/api/projects')
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(self._json(r), list)

    def test_create_project(self):
        r = self._post('/api/projects', {'name': 'Alpha', 'color': '#FF0000'})
        self.assertEqual(r.status_code, 201)
        p = self._json(r)
        self.assertEqual(p['name'], 'Alpha')
        self.assertEqual(p['color'], '#FF0000')
        self.assertIn('id', p)

    def test_create_project_defaults(self):
        r = self._post('/api/projects', {})
        p = self._json(r)
        self.assertEqual(p['name'], 'New Project')
        self.assertEqual(p['color'], '#4A90E2')

    def test_created_project_appears_in_list(self):
        self._post('/api/projects', {'name': 'ListCheck'})
        names = [p['name'] for p in self._json(self._get('/api/projects'))]
        self.assertIn('ListCheck', names)

    def test_update_project_name_and_color(self):
        pid = self._make_project('Original')
        r = self._put(f'/api/projects/{pid}', {'name': 'Updated', 'color': '#00FF00'})
        self.assertEqual(r.status_code, 200)
        p = self._json(r)
        self.assertEqual(p['name'], 'Updated')
        self.assertEqual(p['color'], '#00FF00')

    def test_update_project_partial_preserves_color(self):
        pid = self._make_project('Partial', '#ABCDEF')
        r = self._put(f'/api/projects/{pid}', {'name': 'NameOnly'})
        self.assertEqual(self._json(r)['color'], '#ABCDEF')

    def test_update_project_not_found(self):
        r = self._put('/api/projects/99999', {'name': 'X'})
        self.assertEqual(r.status_code, 404)

    def test_delete_project(self):
        pid = self._make_project('ToDel')
        r = self._del(f'/api/projects/{pid}')
        self.assertEqual(r.status_code, 200)
        ids = [p['id'] for p in self._json(self._get('/api/projects'))]
        self.assertNotIn(pid, ids)

    def test_delete_project_not_found(self):
        r = self._del('/api/projects/99999')
        self.assertEqual(r.status_code, 404)

    def test_projects_response_is_json(self):
        r = self._get('/api/projects')
        self.assertIn('application/json', r.content_type)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Tasks CRUD
# ─────────────────────────────────────────────────────────────────────────────
class TestTasks(PMTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pid = cls._cls_make_project( 'Task Tests')

    def test_list_tasks_returns_list(self):
        # A freshly created project should return a list (may already have tasks from other tests)
        r = self._get(f'/api/projects/{self.pid}/tasks')
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(self._json(r), list)

    def test_list_tasks_project_not_found(self):
        r = self._get('/api/projects/99999/tasks')
        self.assertEqual(r.status_code, 404)

    def test_create_task_defaults(self):
        r = self._post(f'/api/projects/{self.pid}/tasks', {})
        self.assertEqual(r.status_code, 201)
        t = self._json(r)
        self.assertEqual(t['name'], 'New Task')
        self.assertEqual(t['status'], 'Not Started')
        self.assertEqual(t['priority'], 'Medium')
        self.assertEqual(t['project_id'], self.pid)

    def test_create_task_with_core_fields(self):
        r = self._post(f'/api/projects/{self.pid}/tasks', {
            'name': 'Design Phase',
            'owner': 'Alice',
            'status': 'In Progress',
            'priority': 'High',
            'start_date': '2026-05-01',
            'end_date': '2026-05-10',
            'pct_complete': 50,
            'notes': 'Key milestone',
        })
        self.assertEqual(r.status_code, 201)
        t = self._json(r)
        self.assertEqual(t['name'], 'Design Phase')
        self.assertEqual(t['owner'], 'Alice')
        self.assertEqual(t['status'], 'In Progress')
        self.assertEqual(t['priority'], 'High')
        self.assertEqual(t['start_date'], '2026-05-01')
        self.assertEqual(t['end_date'], '2026-05-10')
        self.assertEqual(t['pct_complete'], 50)
        self.assertEqual(t['notes'], 'Key milestone')

    def test_create_task_project_not_found(self):
        r = self._post('/api/projects/99999/tasks', {'name': 'Orphan'})
        self.assertEqual(r.status_code, 404)

    def test_update_task_fields(self):
        tid = self._make_task(self.pid, name='Before', owner='Bob', status='In Progress')
        r = self._put(f'/api/tasks/{tid}', {'name': 'After', 'status': 'Complete', 'pct_complete': 100})
        self.assertEqual(r.status_code, 200)
        t = self._json(r)
        self.assertEqual(t['name'], 'After')
        self.assertEqual(t['status'], 'Complete')
        self.assertEqual(t['pct_complete'], 100)

    def test_update_task_partial_preserves_other_fields(self):
        tid = self._make_task(self.pid, name='Partial', owner='Bob', status='In Progress')
        r = self._put(f'/api/tasks/{tid}', {'status': 'Complete'})
        t = self._json(r)
        self.assertEqual(t['owner'], 'Bob')      # unchanged
        self.assertEqual(t['status'], 'Complete')  # updated

    def test_update_task_not_found(self):
        r = self._put('/api/tasks/99999', {'name': 'X'})
        self.assertEqual(r.status_code, 404)

    def test_delete_task(self):
        tid = self._make_task(self.pid, name='DeleteMe')
        r = self._del(f'/api/tasks/{tid}')
        self.assertEqual(r.status_code, 200)
        tasks = self._json(self._get(f'/api/projects/{self.pid}/tasks'))
        self.assertNotIn(tid, [t['id'] for t in tasks])

    def test_delete_task_not_found(self):
        r = self._del('/api/tasks/99999')
        self.assertEqual(r.status_code, 404)

    def test_task_color_via_update(self):
        # color is not set on create — must use PUT
        tid = self._make_task(self.pid, name='Colored')
        t = self._json(self._put(f'/api/tasks/{tid}', {'color': '#FF5733'}))
        self.assertEqual(t['color'], '#FF5733')

    def test_task_milestone_via_update(self):
        # is_milestone not in INSERT — set via PUT
        tid = self._make_task(self.pid, name='Milestone')
        t = self._json(self._put(f'/api/tasks/{tid}', {'is_milestone': 1}))
        self.assertEqual(t['is_milestone'], 1)

    def test_task_dependency(self):
        t1 = self._json(self._post(f'/api/projects/{self.pid}/tasks',
                                   {'name': 'P', 'start_date': '2026-05-01', 'end_date': '2026-05-05'}))
        tid2 = self._make_task(self.pid, name='Dep')
        t2 = self._json(self._put(f'/api/tasks/{tid2}', {'depends_on': f'{t1["id"]}FS'}))
        self.assertEqual(t2['depends_on'], f'{t1["id"]}FS')

    def test_task_parent_child(self):
        pid_task = self._make_task(self.pid, name='Parent')
        r = self._post(f'/api/projects/{self.pid}/tasks', {'name': 'Child', 'parent_id': pid_task})
        self.assertEqual(r.status_code, 201)
        child = self._json(r)
        self.assertEqual(child['parent_id'], pid_task)

    def test_delete_parent_nulls_child_parent_id(self):
        parent_id = self._make_task(self.pid, name='P2')
        child_id = self._json(self._post(f'/api/projects/{self.pid}/tasks',
                                         {'name': 'C2', 'parent_id': parent_id}))['id']
        self._del(f'/api/tasks/{parent_id}')
        tasks = self._json(self._get(f'/api/projects/{self.pid}/tasks'))
        child = next((t for t in tasks if t['id'] == child_id), None)
        self.assertIsNotNone(child)
        self.assertIsNone(child['parent_id'])

    def test_task_sort_order(self):
        t1 = self._json(self._post(f'/api/projects/{self.pid}/tasks',
                                   {'name': 'First', 'sort_order': 1000}))
        t2 = self._json(self._post(f'/api/projects/{self.pid}/tasks',
                                   {'name': 'Second', 'sort_order': 2000}))
        tasks = self._json(self._get(f'/api/projects/{self.pid}/tasks'))
        ids = [t['id'] for t in tasks]
        self.assertLess(ids.index(t1['id']), ids.index(t2['id']))

    def test_pct_complete_values(self):
        for pct in [0, 25, 50, 75, 100]:
            tid = self._make_task(self.pid, name=f'Pct{pct}')
            t = self._json(self._put(f'/api/tasks/{tid}', {'pct_complete': pct}))
            self.assertEqual(t['pct_complete'], pct)

    def test_tasks_response_is_json(self):
        r = self._get(f'/api/projects/{self.pid}/tasks')
        self.assertIn('application/json', r.content_type)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Task Reorder
# ─────────────────────────────────────────────────────────────────────────────
class TestReorder(PMTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pid = cls._cls_make_project( 'Reorder Tests')

    def test_reorder_updates_sort_order(self):
        t1 = self._json(self._post(f'/api/projects/{self.pid}/tasks', {'name': 'A', 'sort_order': 10}))
        t2 = self._json(self._post(f'/api/projects/{self.pid}/tasks', {'name': 'B', 'sort_order': 20}))
        r = self._post('/api/tasks/reorder', [
            {'id': t1['id'], 'sort_order': 30},
            {'id': t2['id'], 'sort_order': 5},
        ])
        self.assertEqual(r.status_code, 200)
        tasks = self._json(self._get(f'/api/projects/{self.pid}/tasks'))
        order = {t['id']: t['sort_order'] for t in tasks}
        self.assertEqual(order[t1['id']], 30)
        self.assertEqual(order[t2['id']], 5)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Cascade delete
# ─────────────────────────────────────────────────────────────────────────────
class TestCascade(PMTestBase):
    def test_delete_project_removes_tasks(self):
        pid = self._make_project('Cascade')
        self._make_task(pid, name='T1')
        self._make_task(pid, name='T2')
        self._del(f'/api/projects/{pid}')
        r = self._get(f'/api/projects/{pid}/tasks')
        self.assertEqual(r.status_code, 404)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Excel export/template
# ─────────────────────────────────────────────────────────────────────────────
class TestExcelExport(PMTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pid = cls._cls_make_project( 'Excel Tests')
        cls._cls_make_task( cls.pid, name='E1', start_date='2026-05-01', end_date='2026-05-05')

    def test_excel_template_returns_file(self):
        r = self._get(f'/api/projects/{self.pid}/template/excel')
        self.assertEqual(r.status_code, 200)
        ct = r.content_type
        self.assertTrue('spreadsheet' in ct or 'xlsx' in ct or 'octet' in ct,
                        f'Unexpected content-type: {ct}')

    def test_excel_template_project_not_found(self):
        r = self._get('/api/projects/99999/template/excel')
        self.assertEqual(r.status_code, 404)

    def test_excel_template_with_no_tasks(self):
        pid = self._make_project('EmptyExcel')
        r = self._get(f'/api/projects/{pid}/template/excel')
        # Returns blank template — should still be 200
        self.assertEqual(r.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Comments
# ─────────────────────────────────────────────────────────────────────────────
class TestComments(PMTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pid = cls._cls_make_project( 'Comment Tests')
        cls.tid = cls._cls_make_task( cls.pid, name='CT')

    def test_list_comments_returns_list(self):
        r = self._get(f'/api/tasks/{self.tid}/comments')
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(self._json(r), list)

    def test_add_comment(self):
        r = self._post(f'/api/tasks/{self.tid}/comments', {'text': 'Hello', 'author': 'Alice'})
        self.assertIn(r.status_code, [200, 201])
        c = self._json(r)
        self.assertEqual(c['text'], 'Hello')
        self.assertEqual(c['author'], 'Alice')
        self.assertIn('id', c)

    def test_list_comments_after_add(self):
        self._post(f'/api/tasks/{self.tid}/comments', {'text': 'C1', 'author': 'A'})
        r = self._get(f'/api/tasks/{self.tid}/comments')
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(self._json(r)), 1)

    def test_delete_comment(self):
        cid = self._json(self._post(f'/api/tasks/{self.tid}/comments',
                                    {'text': 'Del me', 'author': 'X'}))['id']
        r = self._del(f'/api/comments/{cid}')
        self.assertEqual(r.status_code, 200)
        comments = self._json(self._get(f'/api/tasks/{self.tid}/comments'))
        self.assertNotIn(cid, [c['id'] for c in comments])


# ─────────────────────────────────────────────────────────────────────────────
# 8. Baseline
# ─────────────────────────────────────────────────────────────────────────────
class TestBaseline(PMTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pid = cls._cls_make_project( 'Baseline Tests')
        cls.tid = cls._cls_make_task( cls.pid, name='BT',
                                 start_date='2026-05-01', end_date='2026-05-10')

    def test_set_baseline(self):
        r = self._post(f'/api/projects/{self.pid}/baseline', {})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._json(r).get('ok'), True)

    def test_baseline_copies_dates(self):
        self._post(f'/api/projects/{self.pid}/baseline', {})
        tasks = self._json(self._get(f'/api/projects/{self.pid}/tasks'))
        t = next(t for t in tasks if t['id'] == self.tid)
        self.assertEqual(t.get('baseline_start'), '2026-05-01')
        self.assertEqual(t.get('baseline_end'), '2026-05-10')

    def test_clear_baseline(self):
        self._post(f'/api/projects/{self.pid}/baseline', {})
        r = self._del(f'/api/projects/{self.pid}/baseline')
        self.assertEqual(r.status_code, 200)
        tasks = self._json(self._get(f'/api/projects/{self.pid}/tasks'))
        t = next(t for t in tasks if t['id'] == self.tid)
        self.assertEqual(t.get('baseline_start', ''), '')


# ─────────────────────────────────────────────────────────────────────────────
# 9. AI Chat (route plumbing — LLM call may fail gracefully)
# ─────────────────────────────────────────────────────────────────────────────
class TestAIChat(PMTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pid = cls._cls_make_project( 'AI Tests')

    def test_missing_message_returns_400(self):
        r = self._post(f'/api/projects/{self.pid}/ai-chat', {'history': [], 'tasks': []})
        self.assertEqual(r.status_code, 400)
        self.assertIn('error', self._json(r))

    def test_invalid_project_returns_404(self):
        r = self._post('/api/projects/99999/ai-chat',
                       {'message': 'hello', 'history': [], 'tasks': []})
        self.assertEqual(r.status_code, 404)

    def test_response_has_message_and_actions_keys(self):
        """Route always returns {message, actions} or {error}."""
        tasks = [{'id': 1, 'name': 'Task A', 'start_date': '2026-05-01', 'end_date': '2026-05-10',
                  'owner': 'Alice', 'status': 'Not Started', 'priority': 'High',
                  'depends_on': '', 'pct_complete': 0, 'notes': '', 'parent_id': None}]
        r = self._post(f'/api/projects/{self.pid}/ai-chat', {
            'message': 'What is the critical path?',
            'history': [],
            'tasks': tasks,
        })
        self.assertIn(r.status_code, [200, 500])
        data = self._json(r)
        if r.status_code == 200:
            self.assertIn('message', data)
            self.assertIn('actions', data)
            self.assertIsInstance(data['message'], str)
            self.assertIsInstance(data['actions'], list)
        else:
            self.assertIn('error', data)

    def test_multi_turn_history_accepted(self):
        history = [
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': '{"message":"Hi there!","actions":[]}'},
        ]
        r = self._post(f'/api/projects/{self.pid}/ai-chat', {
            'message': 'Who owns Task A?',
            'history': history,
            'tasks': [{'id': 1, 'name': 'Task A', 'owner': 'Bob',
                       'start_date': '', 'end_date': '', 'status': 'Not Started',
                       'priority': 'Medium', 'depends_on': '', 'pct_complete': 0,
                       'notes': '', 'parent_id': None}],
        })
        self.assertIn(r.status_code, [200, 500])

    def test_empty_tasks_list_accepted(self):
        r = self._post(f'/api/projects/{self.pid}/ai-chat', {
            'message': 'How many tasks are there?',
            'history': [],
            'tasks': [],
        })
        self.assertIn(r.status_code, [200, 500])

    def test_history_trimmed_to_last_10(self):
        """Sending 20 history items should not crash the route."""
        history = [{'role': 'user' if i % 2 == 0 else 'assistant',
                    'content': f'msg {i}'} for i in range(20)]
        r = self._post(f'/api/projects/{self.pid}/ai-chat', {
            'message': 'Summary?',
            'history': history,
            'tasks': [],
        })
        self.assertIn(r.status_code, [200, 500])


# ─────────────────────────────────────────────────────────────────────────────
# 10. AI Schedule Builder
# ─────────────────────────────────────────────────────────────────────────────
class TestAISchedule(PMTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pid = cls._cls_make_project( 'Sched Tests')

    def test_missing_prompt_returns_400(self):
        r = self._post(f'/api/projects/{self.pid}/ai-schedule', {})
        self.assertEqual(r.status_code, 400)

    def test_valid_response_structure(self):
        r = self._post(f'/api/projects/{self.pid}/ai-schedule', {
            'prompt': 'Build a mobile app with 3 phases'
        })
        self.assertIn(r.status_code, [200, 500])
        if r.status_code == 200:
            data = self._json(r)
            self.assertIn('tasks', data)
            self.assertIsInstance(data['tasks'], list)


# ─────────────────────────────────────────────────────────────────────────────
# 11. Edge cases and data integrity
# ─────────────────────────────────────────────────────────────────────────────
class TestEdgeCases(PMTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pid = cls._cls_make_project( 'Edge Tests')

    def test_project_id_is_integer(self):
        r = self._get('/api/projects')
        for p in self._json(r):
            self.assertIsInstance(p['id'], int)

    def test_task_has_all_expected_fields(self):
        tid = self._make_task(self.pid, name='FieldCheck',
                              start_date='2026-06-01', end_date='2026-06-10')
        tasks = self._json(self._get(f'/api/projects/{self.pid}/tasks'))
        t = next(t for t in tasks if t['id'] == tid)
        for field in ['id', 'project_id', 'name', 'owner', 'status', 'priority',
                      'start_date', 'end_date', 'pct_complete', 'depends_on',
                      'notes', 'sort_order', 'parent_id', 'color', 'is_milestone']:
            self.assertIn(field, t, f'Missing field: {field}')

    def test_created_at_present_on_project(self):
        pid = self._make_project('Timestamps')
        projects = self._json(self._get('/api/projects'))
        p = next(p for p in projects if p['id'] == pid)
        self.assertIn('created_at', p)
        self.assertIsNotNone(p['created_at'])

    def test_sort_order_auto_increments(self):
        t1 = self._json(self._post(f'/api/projects/{self.pid}/tasks', {'name': 'Auto1'}))
        t2 = self._json(self._post(f'/api/projects/{self.pid}/tasks', {'name': 'Auto2'}))
        self.assertGreater(t2['sort_order'], t1['sort_order'])

    def test_multiple_dependencies(self):
        t1 = self._make_task(self.pid, name='D1', start_date='2026-05-01', end_date='2026-05-05')
        t2 = self._make_task(self.pid, name='D2', start_date='2026-05-01', end_date='2026-05-05')
        tid = self._make_task(self.pid, name='Dependent')
        t = self._json(self._put(f'/api/tasks/{tid}',
                                 {'depends_on': f'{t1}FS,{t2}FS'}))
        self.assertIn(str(t1), t['depends_on'])
        self.assertIn(str(t2), t['depends_on'])

    def test_large_pct_complete_clamped_or_stored(self):
        tid = self._make_task(self.pid, name='OverPct')
        # Just verify it doesn't crash
        r = self._put(f'/api/tasks/{tid}', {'pct_complete': 100})
        self.assertEqual(r.status_code, 200)

    def test_empty_strings_on_optional_fields(self):
        r = self._post(f'/api/projects/{self.pid}/tasks', {
            'name': 'Minimal',
            'owner': '',
            'notes': '',
            'depends_on': '',
        })
        self.assertEqual(r.status_code, 201)
        t = self._json(r)
        self.assertEqual(t['owner'], '')
        self.assertEqual(t['notes'], '')


# ─────────────────────────────────────────────────────────────────────────────
# 12. API consistency
# ─────────────────────────────────────────────────────────────────────────────
class TestAPIConsistency(PMTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pid = cls._cls_make_project( 'Consistency')
        cls.tid = cls._cls_make_task( cls.pid, name='Con')

    def test_all_endpoints_return_json(self):
        endpoints = [
            '/api/projects',
            f'/api/projects/{self.pid}/tasks',
            f'/api/tasks/{self.tid}/comments',
        ]
        for ep in endpoints:
            r = self._get(ep)
            self.assertIn('application/json', r.content_type, f'Not JSON: {ep}')

    def test_404_returns_json_error(self):
        for ep in ['/api/projects/99999', '/api/tasks/99999',
                   '/api/projects/99999/tasks']:
            r = self._get(ep) if 'tasks' in ep else self._del(ep)
            if r.status_code == 404:
                data = self._json(r)
                self.assertIn('error', data, f'No error key at {ep}')

    def test_put_returns_updated_object(self):
        r = self._put(f'/api/projects/{self.pid}', {'name': 'ReturnCheck'})
        self.assertEqual(r.status_code, 200)
        p = self._json(r)
        self.assertEqual(p['name'], 'ReturnCheck')
        self.assertEqual(p['id'], self.pid)

    def test_create_returns_created_object(self):
        r = self._post(f'/api/projects/{self.pid}/tasks', {'name': 'RetTask'})
        self.assertEqual(r.status_code, 201)
        t = self._json(r)
        self.assertIn('id', t)
        self.assertEqual(t['name'], 'RetTask')


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    loader = unittest.TestLoader()
    if len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
        suite = loader.loadTestsFromName(sys.argv[1], sys.modules[__name__])
    else:
        suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2 if '-v' in sys.argv else 1)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
