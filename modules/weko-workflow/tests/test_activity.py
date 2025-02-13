import pytest
from unittest.mock import Mock, MagicMock, PropertyMock, patch

from flask import jsonify
from flask_login.utils import login_user

from weko_workflow.api import WorkActivity
from weko_workflow.errors import WekoWorkflowException
from weko_workflow.headless import HeadlessActivity
from weko_workflow.models import Activity, ActivityAction, ActivityHistory
from unittest.mock import MagicMock, patch, mock_open
from invenio_files_rest.errors import FileSizeError
from invenio_files_rest.models import Bucket, ObjectVersion
from uuid import uuid4
from unittest.mock import patch, MagicMock

# .tox/c1/bin/pytest --cov=weko_workflow tests/test_activity.py -vv -s --cov-branch --cov-report=term --basetemp=/code/modules/weko-workflow/.tox/c1/tmp

# class HeadlessActivity(WorkActivity):
# .tox/c1/bin/pytest --cov=weko_workflow tests/test_activity.py::TestHeadlessActivity -vv -s --cov-branch --cov-report=term --basetemp=/code/modules/weko-workflow/.tox/c1/tmp
class TestHeadlessActivity:
    # def __init__(self):
    # .tox/c1/bin/pytest --cov=weko_workflow tests/test_activity.py::TestHeadlessActivity::test_init -vv -s --cov-branch --cov-report=term --basetemp=/code/modules/weko-workflow/.tox/c1/tmp
    def test_init(self,app,db,workflow):
        activity = HeadlessActivity()
        assert activity is not None
        assert isinstance(activity._actions, dict)
        assert activity._actions.get(1) == "begin_action"
        assert activity._actions.get(2) == "end_action"
        assert activity._actions.get(3) == "item_login"
        assert activity._actions.get(4) == "approval"
        assert activity._actions.get(5) == "item_link"
        assert activity._actions.get(6) == "oa_policy"
        assert activity._actions.get(7) == "identifier_grant"

    # def init_activity(self, user_id, workflow_id=None, ...):
    # .tox/c1/bin/pytest --cov=weko_workflow tests/test_activity.py::TestHeadlessActivity::test_init_activity -vv -s --cov-branch --cov-report=term --basetemp=/code/modules/weko-workflow/.tox/c1/tmp
    def test_init_activity(self, app, db, workflow, users, client):
        with patch('weko_workflow.views.WorkActivity.get_new_activity_id') as mock_get_new_activity_id:
            mock_get_new_activity_id.side_effect = [f"A-TEST-0000{i}" for i in range(1, 20)]
            login_user(users[1]["obj"])

            assert Activity.query.count() == 0
            assert ActivityHistory.query.count() == 0
            assert ActivityAction.query.count() == 0

            activity = HeadlessActivity()
            assert activity._model is None

            activity.init_activity(users[0]["id"], workflow["workflow"].id)

            assert Activity.query.count() == 1
            assert activity._model is not None
            assert activity._model.activity_login_user == users[0]["id"]
            assert activity.current_action == "item_login"
            assert activity.activity_id == "A-TEST-00001"
            assert activity.detail == "http://test_server.localdomain/workflow/activity/detail/A-TEST-00001"

            activity = HeadlessActivity()

            activity.init_activity(users[0]["id"], workflow["workflow"].id,community="comm01")

            assert Activity.query.count() == 2
            assert activity._model is not None
            assert activity._model.activity_login_user == users[0]["id"]
            assert activity.current_action == "item_login"
            assert activity.activity_id == "A-TEST-00002"
            assert activity.community == "comm01"
            assert activity.detail == "http://test_server.localdomain/workflow/activity/detail/A-TEST-00002?community=comm01"

        with pytest.raises(WekoWorkflowException) as ex:
            activity.init_activity(users[0]["id"], workflow["workflow"].id)
        assert str(ex.value) == "activity is already initialized."

        activity = HeadlessActivity()
        with pytest.raises(WekoWorkflowException) as ex:
            activity.init_activity(users[0]["id"])
        assert str(ex.value) == "workflow_id is required to create activity."

        with pytest.raises(WekoWorkflowException) as ex:
            activity.init_activity(users[0]["id"], 999)
        assert str(ex.value) == "workflow(id=999) is not found."

        with patch("weko_workflow.headless.activity.init_activity") as mock_init_activity:
            mock_init_activity.return_value = jsonify({ "code": -1,"msg":"error"}), 500
            with pytest.raises(WekoWorkflowException) as ex:
                activity.init_activity(users[0]["id"], workflow["workflow"].id)
            assert str(ex.value) == "error"

        with patch("weko_workflow.headless.activity.verify_deletion") as mock_verify_deletion:
            mock_verify_deletion.return_value = jsonify({"is_delete": True})
            with pytest.raises(WekoWorkflowException) as ex:
                activity.init_activity(users[1]["id"], workflow["workflow"].id, activity_id="A-TEST-00001")
            assert str(ex.value) == "activity(A-TEST-00001) is already deleted."

        with patch("weko_workflow.headless.activity.verify_deletion") as mock_verify_deletion:
            mock_verify_deletion.return_value = jsonify({"is_delete": False})
            with patch("weko_workflow.api.WorkActivity.get_activity_by_id") as mock_get_activity_by_id:
                mock_get_activity_by_id.return_value = None
                with pytest.raises(WekoWorkflowException) as ex:
                    activity.init_activity(users[1]["id"], workflow["workflow"].id, activity_id="A-TEST-00001")
                assert str(ex.value) == "activity(A-TEST-00001) is not found."

            with patch("weko_workflow.api.WorkActivity.get_activity_by_id") as mock_get_activity_by_id:
                mock_get_activity_by_id.return_value = MagicMock(activity_login_user=users[1]["id"], shared_user_id=users[1]["id"])
                with patch("weko_workflow.utils.check_authority_by_admin", return_value=False):
                    with pytest.raises(WekoWorkflowException) as ex:
                        activity.init_activity(users[0]["id"], workflow["workflow"].id, activity_id="A-TEST-00001")
                    assert str(ex.value) == f"user({users[0]['id']}) cannot restart activity(A-TEST-00001)."



    #  item_registration(slef, metadata, files, index, comment):
    # .tox/c1/bin/pytest --cov=weko_workflow tests/test_activity.py::TestHeadlessActivity::test_item_registration -vv -s --cov-branch --cov-report=term --basetemp=/code/modules/weko-workflow/.tox/c1/tmp
    def test_item_registration(self, app, db, workflow, users, client, mocker):

        activity = HeadlessActivity()

        with pytest.raises(WekoWorkflowException) as ex:
            activity.item_registration(metadata={}, files=[], index=[], comment="")
        assert str(ex.value) == "activity is not initialized."

        login_user(users[1]["obj"])
        activity.init_activity(users[0]["id"], workflow["workflow"].id)

        with patch("weko_workflow.headless.activity.check_validation_error_msg") as mock_validation_msg:
            msg = ["error<br/>title"]
            error_list = {"mapping": {"title": "error"}}
            mock_validation_msg.return_value = jsonify(code=1, msg=msg, error_list=error_list)
            with pytest.raises(WekoWorkflowException) as ex:
                activity.item_registration(metadata={}, files=[], index=[], comment="")

            assert ex.value.args[0] == {"msg": ["error<br/>title"], "error_list": {"mapping": {"title": "error"}}}

        mock_get_new_activity_id = mocker.patch('weko_workflow.views.WorkActivity.get_new_activity_id')
        mock_get_new_activity_id.side_effect = [f"A-TEST-0000{i}" for i in range(1, 20)]

        patch("weko_workflow.headless.activity.check_validation_error_msg")
        with patch("weko_workflow.headless.activity.HeadlessActivity._input_metadata", return_value=200001):
            with patch("weko_workflow.headless.activity.HeadlessActivity._comment"):
                activity = HeadlessActivity()
                # FIXME: Don't use HeadlessActivity.init_activity, but use WorkActivity.init_activity.
                activity.init_activity(users[0]["id"], workflow["workflow"].id)
                url = activity.item_registration({}, [], [])
                assert activity.recid == 200001
                assert url == "http://test_server.localdomain/workflow/activity/detail/A-TEST-00001"

    # .tox/c1/bin/pytest --cov=weko_workflow tests/test_activity.py::TestHeadlessActivity::test_auto -vv -s --cov-branch --cov-report=term --basetemp=/code/modules/weko-workflow/.tox/c1/tmp
    # def auto(self, **params):
    def test_auto(self, app, workflow, mocker):
        original_detail = HeadlessActivity.detail
        original_current_action = HeadlessActivity.current_action

        detail = "http://test_server.localdomain/workflow/activity/detail/A-TEST-00001"
        actions = ["item_login"] * 2 + ["item_link"] * 3 + ["identifier_grant"] * 4 + ["end_action"] * 2

        # Flow of actions: start_action -> item_login -> item_link -> identifier_grant -> end_action
        activity = HeadlessActivity()
        mock_detail = PropertyMock(return_value=detail)
        mock_current_action = PropertyMock(side_effect=actions)
        mocker.patch("weko_workflow.headless.activity.HeadlessActivity.init_activity")

        mock_init_activity = MagicMock()
        mock_item_registration = MagicMock()
        mock_item_link = MagicMock()
        mock_identifier_grant = MagicMock()
        mock_oa_policy = MagicMock()
        mock_end = MagicMock()

        activity.init_activity = mock_init_activity
        activity.item_registration = mock_item_registration
        activity.item_link = mock_item_link
        activity.identifier_grant = mock_identifier_grant
        activity.oa_policy = mock_oa_policy
        activity.end = mock_end

        type(activity).detail = mock_detail
        type(activity).current_action = mock_current_action

        url, current_action, _ = activity.auto(user_id=1, workflow_id=1)
        assert url == detail
        assert current_action == "end_action"

        assert mock_init_activity.call_count == 1
        assert mock_item_registration.call_count == 1
        assert mock_item_link.call_count == 1
        assert mock_identifier_grant.call_count == 1
        assert mock_oa_policy.call_count == 0
        assert mock_end.call_count == 1

        # Flow of actions: start_action -> item_login -> item_link -> oa_policy -> approval -> end_action
        # Stop at approval
        detail = "http://test_server.localdomain/workflow/activity/detail/A-TEST-00002"
        actions = ["item_login"] * 2 + ["item_link"] * 3 + ["oa_policy"] * 5 + ["approval"] * 2

        activity = HeadlessActivity()
        mock_detail = PropertyMock(return_value=detail)
        mock_current_action = PropertyMock(side_effect=actions)
        mocker.patch("weko_workflow.headless.activity.HeadlessActivity.init_activity")

        mock_init_activity = MagicMock()
        mock_item_registration = MagicMock()
        mock_item_link = MagicMock()
        mock_identifier_grant = MagicMock()
        mock_oa_policy = MagicMock()
        mock_end = MagicMock()

        activity.init_activity = mock_init_activity
        activity.item_registration = mock_item_registration
        activity.item_link = mock_item_link
        activity.oa_policy = mock_oa_policy
        activity.end = mock_end

        type(activity).detail = mock_detail
        type(activity).current_action = mock_current_action

        url, current_action, _ = activity.auto(user_id=1, workflow_id=1)
        assert url == detail
        assert current_action == "approval"

        assert mock_init_activity.call_count == 1
        assert mock_item_registration.call_count == 1
        assert mock_item_link.call_count == 1
        assert mock_identifier_grant.call_count == 0
        assert mock_oa_policy.call_count == 1
        assert mock_end.call_count == 1

        # continue from item_link
        detail = "http://test_server.localdomain/workflow/activity/detail/A-TEST-00003"
        actions = ["item_link"] * 3 + ["end_action"] * 2

        activity = HeadlessActivity()
        mock_detail = PropertyMock(return_value=detail)
        mock_current_action = PropertyMock(side_effect=actions)
        mocker.patch("weko_workflow.headless.activity.HeadlessActivity.init_activity")

        mock_init_activity = MagicMock()
        mock_item_registration = MagicMock()
        mock_item_link = MagicMock()
        mock_identifier_grant = MagicMock()
        mock_oa_policy = MagicMock()
        mock_end = MagicMock()

        activity.init_activity = mock_init_activity
        activity.item_link = mock_item_link
        activity.end = mock_end

        type(activity).detail = mock_detail
        type(activity).current_action = mock_current_action

        url, current_action, _ = activity.auto(user_id=1, workflow_id=1)
        assert url == detail
        assert current_action == "end_action"

        assert mock_init_activity.call_count == 1
        assert mock_item_registration.call_count == 0
        assert mock_item_link.call_count == 1
        assert mock_identifier_grant.call_count == 0
        assert mock_oa_policy.call_count == 0
        assert mock_end.call_count == 1

        type(activity).detail = original_detail
        type(activity).current_action = original_current_action

    # .tox/c1/bin/pytest --cov=weko_workflow tests/test_activity.py::TestHeadlessActivity::test__input_metadata -vv -s --cov-branch --cov-report=term --basetemp=/code/modules/weko-workflow/.tox/c1/tmp
    def test__input_metadata(self, app, db, workflow, users, client, mocker):
        mocker.patch.object(HeadlessActivity,"_upload_files",return_value=[{"file_name": "test.txt", "file_id": "12345"}])
        mocker.patch("weko_workflow.api.WorkActivity.upt_activity_metadata", return_value=None)
        mocker.patch("weko_workflow.headless.activity.get_workflow_journal", return_value=None)
        mocker.patch("weko_workflow.headless.activity.get_feedback_maillist", return_value=(MagicMock(json={"code": 1, "data": []}), None))
        mocker.patch("weko_workflow.headless.activity.get_mapping", return_value={"title.@value": "title"})
        mocker.patch("weko_workflow.headless.activity.get_data_by_property", return_value=(["Test Title"], None))
        mocker.patch("weko_workflow.headless.activity.current_pidstore.minters", {"weko_deposit_minter": lambda record_uuid, data: MagicMock(pid_value="200001")})
        mocker.patch("weko_workflow.headless.activity.WekoDeposit.create", return_value=MagicMock())
        mocker.patch("weko_workflow.headless.activity.WekoDeposit.update")
        mocker.patch("weko_workflow.headless.activity.WekoDeposit.commit")
        mocker.patch("weko_workflow.headless.activity.update_cache_data")
        mocker.patch("weko_workflow.headless.activity.delete_user_lock_activity_cache")
        mocker.patch("weko_workflow.headless.activity.delete_lock_activity_cache")
        with patch('weko_workflow.views.WorkActivity.get_new_activity_id') as mock_get_new_activity_id:
            # case 1
            mocker.patch("weko_workflow.headless.activity.validate_form_input_data", side_effect=lambda result, itemtype_id, metadata: result.update({"is_valid": True}))
            mock_get_new_activity_id.side_effect = [f"A-TEST-0000{i}" for i in range(1, 20)]
            login_user(users[1]["obj"])
            activity = HeadlessActivity()

            activity.init_activity(users[1]["id"], workflow["workflow"].id,community="comm01")

            metadata = {
                "title": "Test Title",
                "pubdate": "2024-01-01",
                "shared_user_id": users[1]["id"]
            }
            files = []
            recid = activity._input_metadata(metadata, files)
            assert recid == "200001"

            # files is None
            mocker.patch("weko_workflow.headless.activity.validate_form_input_data", side_effect=lambda result, itemtype_id, metadata: result.update({"is_valid": True}))
            files = None
            recid = activity._input_metadata(metadata, files)
            assert recid == "200001"

            # input_metadata_invalid
            mocker.patch("weko_workflow.headless.activity.validate_form_input_data", side_effect=lambda result, itemtype_id, metadata: result.update({"is_valid": False, "error": "Invalid metadata"}))
            with pytest.raises(WekoWorkflowException) as ex:
                activity._input_metadata(metadata, files)
            assert str(ex.value) == "failed to input metadata: Invalid metadata"

            # TODO: metadata_existing_record
            # activity.recid = "200001"
            # mocker.patch("weko_workflow.headless.activity.validate_form_input_data", side_effect=lambda result, itemtype_id, metadata: result.update({"is_valid": True}))
            # recid = activity._input_metadata(metadata, files)
            # assert recid == "200001"

            # TODO: SQLAlchemyError occurs in try block

    # .tox/c1/bin/pytest --cov=weko_workflow tests/test_activity.py::TestHeadlessActivity::test__upload_files -vv -s --cov-branch --cov-report=term --basetemp=/code/modules/weko-workflow/.tox/c1/tmp
    def test__upload_files(self, app, db, workflow, users, client, mocker):

        activity = HeadlessActivity()
        activity._deposit = {"_buckets": {"deposit": uuid4()}}  # UUIDを設定
        mocker.patch.object(Bucket, "query", new=Mock())
        mock_bucket = Mock(spec=Bucket)
        mock_bucket.size_limit = 1000
        mock_bucket.location.max_file_size = 500
        mocker.patch.object(Bucket.query, "get", return_value=mock_bucket)
        mock_object_version = MagicMock()
        mock_object_version.basename="test.txt"
        mocker.patch("weko_workflow.headless.activity.ObjectVersion.create", return_value=mock_object_version)
        mocker.patch("weko_workflow.headless.activity.ObjectVersion.set_contents")

        # Test case: file size exceeds limit
        with pytest.raises(FileSizeError) as ex:
            activity._upload_files([MagicMock(filename="test.txt", stream=mock_open(read_data="data"), content_length=501)])
        assert "File size limit exceeded." in str(ex.value)

        # Test case: file not found
        with pytest.raises(WekoWorkflowException) as ex:
            activity._upload_files(["non_existent_file.txt"])
        print(ex.value)
        assert str(ex.value) == "file(non_existent_file.txt) is not found."

        # Test case: successful upload with file path
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.path.getsize", return_value=10)
        with patch("builtins.open", mock_open(read_data="data")):
            files_info = activity._upload_files(["test.txt"])
            assert len(files_info) == 1
            print(files_info)
            assert files_info[0]["filename"] == "test.txt"

        # Test case: successful upload with FileStorage object
        file_storage = MagicMock(filename="test.txt", stream=mock_open(read_data="data"), content_length=10)
        files_info = activity._upload_files([file_storage])
        assert len(files_info) == 1
        assert files_info[0]["filename"] == "test.txt"

        # # Test case: file size within limit
        # mock_bucket.size_limit = 100
        # mock_bucket.location.max_file_size = 200
        # mocker.patch.object(Bucket.query, "get", return_value=mock_bucket)
        # file_storage = MagicMock(filename="test.txt", stream=mock_open(read_data="data"), content_length=50)
        # files_info = activity._upload_files([file_storage])
        # assert len(files_info) == 1
        # assert files_info[0]["filename"] == "test.txt"

        # # Test case: file size exceeds location limit
        # mock_bucket.size_limit = 100
        # mock_bucket.location.max_file_size = 50
        # file_storage = MagicMock(filename="test.txt", stream=mock_open(read_data="data"), content_length=60)
        # with pytest.raises(FileSizeError):
        #     activity._upload_files([file_storage])


    # .tox/c1/bin/pytest --cov=weko_workflow tests/test_activity.py::TestHeadlessActivity::test__designate_index -vv -s --cov-branch --cov-report=term --basetemp=/code/modules/weko-workflow/.tox/c1/tmp
    def test__designate_index(self, app, db, workflow, users, client, mocker):
        activity = HeadlessActivity()

        login_user(users[1]["obj"])
        activity.init_activity(users[1]["id"], workflow["workflow"].id)

        # Mocking the necessary methods
        mock_user_lock = mocker.patch.object(activity, "_user_lock")
        mock_activity_lock = mocker.patch.object(activity, "_activity_lock", return_value="locked_value")
        mock_user_unlock = mocker.patch.object(activity, "_user_unlock")
        mock_activity_unlock = mocker.patch.object(activity, "_activity_unlock")
        mock_update_index_tree_for_record = mocker.patch("weko_workflow.headless.activity.update_index_tree_for_record")

        # Test case: index is not a list
        # FIXME: index is int
        activity._designate_index("index1")
        mock_update_index_tree_for_record.assert_called_once_with(activity.recid, "index1")

        # Test case: index is a list
        # FIXME: index is list[int]
        activity._designate_index(["index1", "index2"])
        assert mock_update_index_tree_for_record.call_count == 3
        mock_update_index_tree_for_record.assert_any_call(activity.recid, "index1")
        mock_update_index_tree_for_record.assert_any_call(activity.recid, "index2")

        # Verify locks and unlocks
        assert mock_user_lock.call_count == 2
        assert mock_activity_lock.call_count == 2
        assert mock_user_unlock.call_count == 2
        assert mock_activity_unlock.call_count == 2
        mock_activity_unlock.assert_any_call("locked_value")

        # TODO: SQLAlchemyError occurs in update_index_tree_for_record

    # .tox/c1/bin/pytest --cov=weko_workflow tests/test_activity.py::TestHeadlessActivity::test__comment -vv -s --cov-branch --cov-report=term --basetemp=/code/modules/weko-workflow/.tox/c1/tmp
    def test__comment(self, app, db, workflow, users, client, mocker):
        activity = HeadlessActivity()

        login_user(users[1]["obj"])
        activity.init_activity(users[1]["id"], workflow["workflow"].id)

        # Mocking the necessary methods
        mock_user_lock = mocker.patch.object(activity, "_user_lock")
        mock_activity_lock = mocker.patch.object(activity, "_activity_lock", return_value="locked_value")
        mock_user_unlock = mocker.patch.object(activity, "_user_unlock")
        mock_activity_unlock = mocker.patch.object(activity, "_activity_unlock")
        mock_next_action = mocker.patch("weko_workflow.headless.activity.next_action", return_value=(MagicMock(json={"code": 0, "msg": ""}), None))
        # Test case: successful comment
        activity._comment("This is a test comment")
        mock_next_action.assert_called_once_with(activity.activity_id, activity.current_action_id, {"commond": "This is a test comment"})
        mock_user_lock.assert_called_once()
        mock_activity_lock.assert_called_once()
        mock_user_unlock.assert_called_once()
        mock_activity_unlock.assert_called_once_with("locked_value")

        # Test case: failed to set comment
        mock_next_action.return_value = (MagicMock(json={"code": 1, "msg": "error"}), None)
        with pytest.raises(WekoWorkflowException) as ex:
            activity._comment("This is a test comment")
        assert str(ex.value) == "error"
        mock_user_lock.assert_called()
        mock_activity_lock.assert_called()
        mock_user_unlock.assert_called()
        mock_activity_unlock.assert_called_with("locked_value")

        # TODO: SQLAlchemyError occurs in next_action

    # .tox/c1/bin/pytest --cov=weko_workflow tests/test_activity.py::TestHeadlessActivity::test_item_link -vv -s --cov-branch --cov-report=term --basetemp=/code/modules/weko-workflow/.tox/c1/tmp
    def test_item_link(self, app, db, workflow, users, client, mocker):
        activity = HeadlessActivity()

        login_user(users[1]["obj"])
        activity.init_activity(users[1]["id"], workflow["workflow"].id)

        # Mocking the necessary methods
        mock_user_lock = mocker.patch.object(activity, "_user_lock")
        mock_activity_lock = mocker.patch.object(activity, "_activity_lock", return_value="locked_value")
        mock_user_unlock = mocker.patch.object(activity, "_user_unlock")
        mock_activity_unlock = mocker.patch.object(activity, "_activity_unlock")
        mock_next_action = mocker.patch("weko_workflow.headless.activity.next_action", return_value=(MagicMock(json={"code": 0, "msg": ""}), None))

        # Test case: successful item link
        link_data = [{"link": "test_link"}]
        activity.item_link(link_data)
        mock_next_action.assert_called_once_with(activity.activity_id, activity.current_action_id, {"link_data": link_data})
        mock_user_lock.assert_called_once()
        mock_activity_lock.assert_called_once()
        mock_user_unlock.assert_called_once()
        mock_activity_unlock.assert_called_once_with("locked_value")

        # Test case: failed item link
        mock_next_action.return_value = (MagicMock(json={"code": 1, "msg": "error"}), None)
        with pytest.raises(WekoWorkflowException) as ex:
            activity.item_link(link_data)
        assert str(ex.value) == "error"
        mock_user_lock.assert_called()
        mock_activity_lock.assert_called()
        mock_user_unlock.assert_called()
        mock_activity_unlock.assert_called_with("locked_value")

        # TODO: SQLAlchemyError occurs in next_action


    def test_approval(self):
        pass

    def test_oa_policy(self):
        pass

    # .tox/c1/bin/pytest --cov=weko_workflow tests/test_activity.py::TestHeadlessActivity::test_identifier_grant -vv -s --cov-branch --cov-report=term --basetemp=/code/modules/weko-workflow/.tox/c1/tmp
    def test_identifier_grant(self, app, db, workflow, users, client, mocker):
        activity = HeadlessActivity()

        login_user(users[1]["obj"])
        activity.init_activity(users[1]["id"], workflow["workflow"].id)

        # Mocking the necessary methods
        mock_user_lock = mocker.patch.object(activity, "_user_lock")
        mock_activity_lock = mocker.patch.object(activity, "_activity_lock", return_value="locked_value")
        mock_user_unlock = mocker.patch.object(activity, "_user_unlock")
        mock_activity_unlock = mocker.patch.object(activity, "_activity_unlock")
        mock_next_action = mocker.patch("weko_workflow.headless.activity.next_action", return_value=(MagicMock(json={"code": 0, "msg": ""}), None))

        # Test case: successful identifier grant
        grant_data = {"identifier_grant": "1"}
        activity.identifier_grant(grant_data)
        mock_next_action.assert_called_once_with(activity.activity_id, activity.current_action_id, grant_data)
        mock_user_lock.assert_called_once()
        mock_activity_lock.assert_called_once()
        mock_user_unlock.assert_called_once()
        mock_activity_unlock.assert_called_once_with("locked_value")

        # Test case: failed identifier grant
        mock_next_action.return_value = (MagicMock(json={"code": 1, "msg": "error"}), None)
        with pytest.raises(WekoWorkflowException) as ex:
            activity.identifier_grant(grant_data)
        assert str(ex.value) == "error"
        mock_user_lock.assert_called()
        mock_activity_lock.assert_called()
        mock_user_unlock.assert_called()
        mock_activity_unlock.assert_called_with("locked_value")

    # def end(self):
    # .tox/c1/bin/pytest --cov=weko_workflow tests/test_activity.py::TestHeadlessActivity::test_end -vv -s --cov-branch --cov-report=term --basetemp=/code/modules/weko-workflow/.tox/c1/tmp
    def test_end(self, app, db, workflow, users, client):
        with patch('weko_workflow.views.WorkActivity.get_new_activity_id') as mock_get_new_activity_id:
            mock_get_new_activity_id.side_effect = [f"A-TEST-0000{i}" for i in range(1, 20)]
            login_user(users[1]["obj"])
            activity = HeadlessActivity()
            act_data = {
                "workflow_id": workflow["workflow"].id,
                "flow_id": workflow["workflow"].flow_id,
                "itemtype_id": workflow["workflow"].itemtype_id,
                "activity_login_user": users[0]["id"],
            }
            activity.user = users[0]["obj"]
            activity._model = WorkActivity().init_activity(act_data)
            assert activity.user is not None
            assert activity.activity_id == "A-TEST-00001"
            assert activity.detail != ""
            assert activity.current_action == "item_login"

            activity.end()

            assert activity.user is None
            assert activity._model is None
            assert activity.activity_id == None
            assert activity.detail == ""
            assert activity.current_action == None

    # # .tox/c1/bin/pytest --cov=weko_workflow tests/test_activity.py::TestHeadlessActivity::test_auto -vv -s --cov-branch --cov-report=term --basetemp=/code/modules/weko-workflow/.tox/c1/tmp
    # def test_auto(self, app, db, workflow, users, client, mocker):
    #     activity = HeadlessActivity()

    #     login_user(users[1]["obj"])
    #     # activity.init_activity(users[1]["id"], workflow["workflow"].id)

    #     # Mocking the necessary methods
    #     mock_user_lock = mocker.patch.object(activity, "_user_lock")
    #     mock_activity_lock = mocker.patch.object(activity, "_activity_lock", return_value="locked_value")
    #     mock_user_unlock = mocker.patch.object(activity, "_user_unlock")
    #     mock_activity_unlock = mocker.patch.object(activity, "_activity_unlock")
    #     mock_end = mocker.patch.object(activity, "end")
    #     mock_item_registration = mocker.patch.object(activity, "item_registration")
    #     mock_item_link = mocker.patch.object(activity, "item_link")
    #     mock_identifier_grant = mocker.patch.object(activity, "identifier_grant")
    #     mock_oa_policy = mocker.patch.object(activity, "oa_policy")

    #     # Test case: current_action is "end_action"
    #     activity._model = MagicMock()
    #     activity._model.action_id = 2  # Assuming 2 corresponds to "end_action"
    #     result = activity.auto(user_id=users[1]["id"], workflow_id=workflow["workflow"].id)

        # FIXME: assert return value and expected value
        """ activity.detailとself.detail　などは戻り値とインスタンス変数は必ず同じ値なので assert しても意味がありません
            113行目に既にテストを行っているので、ここで追加のautoメソッドのテストは不要です　黒田
        """
        # assert result == (activity.detail, activity.current_action, activity.recid)
        # mock_user_lock.assert_called_once()
        # mock_activity_lock.assert_called_once()
        # mock_user_unlock.assert_called_once()
        # mock_activity_unlock.assert_called_once_with("locked_value")
        # mock_end.assert_called_once()

        # # Test case: current_action is "approval"
        # activity._model.action_id = 4  # Assuming 4 corresponds to "approval"
        # result = activity.auto(user_id=users[1]["id"], workflow_id=workflow["workflow"].id)
        # assert result == (activity.detail, activity.current_action, activity.recid)
        # mock_user_lock.assert_called()
        # mock_activity_lock.assert_called()
        # mock_user_unlock.assert_called()
        # mock_activity_unlock.assert_called_with("locked_value")
        # mock_end.assert_called()

        # # Test case: current_action is "item_login"
        # activity._model.action_id = 3  # Assuming 3 corresponds to "item_login"
        # result = activity.auto(user_id=users[1]["id"], workflow_id=workflow["workflow"].id, metadata={}, files=[], index=[], comment="")
        # assert mock_item_registration.called
        # assert result == (activity.detail, activity.current_action, activity.recid)
        # mock_user_lock.assert_called()
        # mock_activity_lock.assert_called()
        # mock_user_unlock.assert_called()
        # mock_activity_unlock.assert_called_with("locked_value")
        # mock_end.assert_called()

        # # Test case: current_action is "item_link"
        # activity._model.action_id = 5  # Assuming 5 corresponds to "item_link"
        # result = activity.auto(user_id=users[1]["id"], workflow_id=workflow["workflow"].id, link_data=[])
        # assert mock_item_link.called
        # assert result == (activity.detail, activity.current_action, activity.recid)
        # mock_user_lock.assert_called()
        # mock_activity_lock.assert_called()
        # mock_user_unlock.assert_called()
        # mock_activity_unlock.assert_called_with("locked_value")
        # mock_end.assert_called()

        # # Test case: current_action is "identifier_grant"
        # activity._model.action_id = 7  # Assuming 7 corresponds to "identifier_grant"
        # result = activity.auto(user_id=users[1]["id"], workflow_id=workflow["workflow"].id, grant_data={})
        # assert mock_identifier_grant.called
        # assert result == (activity.detail, activity.current_action, activity.recid)
        # mock_user_lock.assert_called()
        # mock_activity_lock.assert_called()
        # mock_user_unlock.assert_called()
        # mock_activity_unlock.assert_called_with("locked_value")
        # mock_end.assert_called()

        # # Test case: current_action is "oa_policy"
        # activity._model.action_id = 6  # Assuming 6 corresponds to "oa_policy"
        # result = activity.auto(user_id=users[1]["id"], workflow_id=workflow["workflow"].id, policy={})
        # assert mock_oa_policy.called
        # assert result == (activity.detail, activity.current_action, activity.recid)
        # mock_user_lock.assert_called()
        # mock_activity_lock.assert_called()
        # mock_user_unlock.assert_called()
        # mock_activity_unlock.assert_called_with("locked_value")
        # mock_end.assert_called()

        # # Test case: failed to progress the action
        # activity._model.action_id = 3  # Assuming 3 corresponds to "item_login"
        # mock_item_registration.side_effect = Exception("failed to progress the action.")
        # with pytest.raises(Exception) as ex:
        #     activity.auto(user_id=users[1]["id"], workflow_id=workflow["workflow"].id, metadata={}, files=[], index=[], comment="")
        # assert str(ex.value) == "failed to progress the action."
        # mock_user_lock.assert_called()
        # mock_activity_lock.assert_called()
        # mock_user_unlock.assert_called()
        # mock_activity_unlock.assert_called_with("locked_value")
        # mock_end.assert_called()
