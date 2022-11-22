from .admin import ProjectAdmin
from .admin import ProjectParticipantsResource
from .admin import YearFilter
from .models import MediaEducationSupervisor
from .models import Project
from .models import ProjectParticipant
from datetime import datetime
from datetime import timedelta
from django.urls import reverse_lazy
from ok_tools.datetime import TZ
from ok_tools.testing import DOMAIN
from ok_tools.testing import create_project
from registration.models import Gender
from unittest.mock import patch
import pytest


A_PROJ_URL = f'{DOMAIN}{reverse_lazy("admin:projects_project_changelist")}'


def test__admin__1(browser):
    """It is possible to add project and project deps."""
    browser.login_admin()
    base_url = browser.url
    browser.open(f'{base_url}projects/projectleader/add')
    browser.getControl('name').value = 'Hans im Glück'
    browser.getControl(name='_save').click()
    browser.open(f'{base_url}projects/mediaeducationsupervisor/add')
    browser.getControl('name').value = 'Heinz im Glück'
    browser.getControl(name='_save').click()
    browser.open(f'{base_url}projects/projectcategory/add')
    browser.getControl('Project category').value = 'Hauptkategorie'
    browser.getControl(name='_save').click()
    browser.open(f'{base_url}projects/targetgroup/add')
    browser.getControl('Target group').value = 'Die wichtige Zielgruppe'
    browser.getControl(name='_save').click()
    browser.open(f'{base_url}projects/project/add')
    browser.getControl(name='_save').click()


def test__projects__admin__YearFilter__1(browser, project_dict):
    """Projects can be filtered by the year of the start date."""
    project_dict['title'] = 'new_title'
    project_dict['begin_date'] = datetime(
        year=datetime.now().year, month=9, day=20, hour=9, tzinfo=TZ)
    proj1 = create_project(project_dict)

    project_dict['title'] = 'old_title'
    project_dict['begin_date'] = datetime(
        year=datetime.now().year-1, month=9, day=20, hour=9, tzinfo=TZ)
    proj2 = create_project(project_dict)

    browser.login_admin()
    browser.open(A_PROJ_URL)

    browser.follow('This year')
    assert proj1.title in browser.contents
    assert proj2.title not in browser.contents

    browser.follow('Last year')
    assert proj1.title not in browser.contents
    assert proj2.title in browser.contents


def test__projects__admin__YearFilter__2():
    """Handle invalid values."""
    with patch.object(YearFilter, 'value', return_value='invalid'):
        with pytest.raises(ValueError, match=r'Invalid value .*'):
            filter = YearFilter(
                {}, {}, Project, ProjectAdmin)
            filter.queryset(None, None)


def test__projects__admin__ProjectResource__1(browser, project_dict):
    """Export projects."""
    s1 = MediaEducationSupervisor.objects.create(name='supervisor1')
    s2 = MediaEducationSupervisor.objects.create(name='supervisor2')
    supervisors = [s1, s2]

    create_project(project_dict, supervisors)

    browser.login_admin()
    browser.open(A_PROJ_URL)

    browser.follow('Export')
    browser.getControl('csv').click()
    browser.getControl('Submit').click()

    assert browser.headers['Content-Type'] == 'text/csv'
    assert str(s1) in str(browser.contents)
    assert str(s2) in str(browser.contents)


def test__projects__admin__ProjectResource__2(browser, project_dict):
    """Export all necessary data."""
    project: Project = create_project(project_dict)
    browser.login_admin()
    browser.open(A_PROJ_URL)

    browser.follow('Export')
    browser.getControl('csv').click()
    browser.getControl('Submit').click()

    assert browser.headers['Content-Type'] == 'text/csv'
    export = str(browser.contents)
    assert project.title in export
    assert project.topic in export
    assert str(project.duration) in export
    assert str(project.begin_date.time()) in export
    assert str(project.end_date.time()) in export
    assert str(project.external_venue) in export
    assert str(project.jugendmedienschutz) in export
    assert str(project.target_group) in export
    assert str(project.project_category) in export
    assert str(project.project_leader) in export


def test__projects__admin__ProjectParticipantsResource__1(
        browser, project_dict):
    """Export all participants of a project."""
    no_participant = ProjectParticipant.objects.create(name='no participant')
    participant = ProjectParticipant.objects.create(
        name='participant',
        age=24,
        gender='f',
    )
    project: Project = create_project(project_dict, participants=[participant])
    project_dict['title'] = 'without participants'
    without_participants: Project = create_project(project_dict)

    browser.login_admin()
    browser.open(A_PROJ_URL)
    browser.follow('Export')
    # Select Project Participants
    browser.getControl('Project Participants').click()
    browser.getControl('csv').click()
    browser.getControl('Submit').click()

    assert browser.headers['Content-Type'] == 'text/csv'
    export = str(browser.contents)
    assert no_participant.name not in export
    assert project.title in export
    assert str(project.begin_date.date()) in export
    assert participant.name in export
    assert str(participant.age) in export
    assert str(Gender.verbose_name(participant.gender)) in export
    assert without_participants.title not in export

    without_queryset = ProjectParticipantsResource().export().get_csv()
    assert bytes(without_queryset, 'utf-8') == browser.contents


def test__projects__models__1(db, project):
    """Project gets represented by its title."""
    assert str(project) == project.title


@pytest.mark.parametrize("age,gender,expected_age,expected_gender",
                         [
                             (6, 'm', '0_bis_6', 0),
                             (10, 'f', '7_bis_10', 1),
                             (14, 'd', '11_bis_14', 2),
                             (18, 'd', '15_bis_18', 2),
                             (34, 'd', '19_bis_34', 2),
                             (50, 'd', '35_bis_50', 2),
                             (65, 'd', '51_bis_65', 2),
                             (66, 'd', 'ueber_65', 2),
                         ]
                         )
def test__projects__signals__update_age_and_gender__1(
        db, project_dict, age, gender, expected_age, expected_gender):
    """After adding a participant the age and gender fields get updated."""
    participant: ProjectParticipant = ProjectParticipant.objects.create(
        name="Testname",
        age=age,
        gender=gender,
    )
    project: Project = create_project(
        project_dict, participants=[participant])

    assert project.statistic.get(expected_age)[expected_gender] == 1


def test__projects__signals__update_age_and_gender__2(
        db, project_dict):
    """After adding a participant the age and gender fields get updated."""
    participant: ProjectParticipant = ProjectParticipant.objects.create(
        name="Testname")
    project: Project = create_project(
        project_dict, participants=[participant])

    assert project.statistic.get('not_given')[3] == 1


def test__projects__signals__update_age_and_gender__3(
        db, project_dict):
    """If a participant gets removed, the statistic gets updated."""
    participant: ProjectParticipant = ProjectParticipant.objects.create(
        name="Testname",
        age=24,
        gender='m',
    )
    project: Project = create_project(
        project_dict, participants=[participant])

    assert project.statistic.get('19_bis_34')[0] == 1
    project.participants.remove(participant)
    assert project.statistic.get('19_bis_34')[0] == 0


def test__projects__signals__update_age_and_gender__4(db, project_dict):
    """Adding a participant with an unknown gender."""
    participant: ProjectParticipant = ProjectParticipant.objects.create(
        name="Testname",
        gender="unknown",
    )
    with pytest.raises(ValueError, match=r'Unknown gender .*'):
        create_project(project_dict, participants=[participant])


def test__projects__admin__ProjectAdmin__1(browser, project):
    """Export the projects date to ics."""
    browser.login_admin()
    browser.open(A_PROJ_URL)
    browser.follow('Export dates')

    begin_date = project.begin_date
    assert browser.headers['Content-Type'] == 'text/calendar'
    assert project.title in str(browser.contents)
    assert str(begin_date.tzinfo) in str(browser.contents)
    assert _f_ics_date(begin_date) in str(browser.contents)
    assert project.topic in str(browser.contents)


def test__projects__admin__ProjectAdmin__2(browser, project_dict):
    """Export the projects date of this year to ics."""
    project_dict['begind_date'] = datetime(
        year=datetime.now().year,
        month=9,
        day=26,
        tzinfo=TZ,
    )
    project_dict['title'] = 'new_project'
    proj1 = create_project(project_dict)

    project_dict['begin_date'] = datetime(
        year=datetime.now().year-1,
        month=9,
        day=26,
        tzinfo=TZ,
    )
    project_dict['title'] = 'old_project'
    proj2 = create_project(project_dict)

    browser.login_admin()
    browser.open(A_PROJ_URL)
    browser.follow('This year')
    browser.follow('Export dates')

    assert browser.headers['Content-Type'] == 'text/calendar'
    assert proj1.title in str(browser.contents)
    assert proj2.title not in str(browser.contents)


def test__projects__admin__ProjectAdmin__3(browser, project):
    """Export the project date without accessing the admin site."""
    browser.login_admin()
    browser.open(f'{DOMAIN}{reverse_lazy("admin:calender_export")}')

    assert browser.headers['Content-Type'] == 'text/calendar'
    assert project.title in str(browser.contents)


def test__projects__admin__ProjectAdmin__4(browser, project):
    """The export dates button only appears on the project site."""
    browser.login_admin()
    browser.open(f'{DOMAIN}{reverse_lazy("contributions:contributions")}')

    assert 'Export dates' not in browser.contents


def test__projects__admin__ProjectAdmin__6(browser, project_dict):
    """The duration and end_date does not match."""
    project_dict['begin_date'] = datetime(
        year=2022,
        month=9,
        day=3,
        hour=9,
        tzinfo=TZ
    )
    project_dict['end_date'] = datetime(
        year=2022,
        month=9,
        day=3,
        hour=10,
        tzinfo=TZ
    )
    project_dict['duration'] = timedelta(hours=1, minutes=30)

    project = create_project(project_dict)

    browser.login_admin()
    browser.open(A_PROJ_URL)
    browser.follow('Export dates')

    assert browser.headers['Content-Type'] == 'text/calendar'
    assert _f_ics_date(project.end_date) in str(browser.contents)


def test__projects__models__ProjectParticipant____str____1(db):
    """A project participant get represented by name, age and gender."""
    part = ProjectParticipant.objects.create(
        name='test name',
        age=27,
        gender='d',
    )

    assert (f'{part.name} ({part.age}, {Gender.verbose_name(part.gender)})'
            == str(part))


def test__projects__models__Project__statistic_key_to_label__1():
    """Trying to convert an invalid key value results in an ValueError."""
    INVALID = 'invalid'
    with pytest.raises(ValueError, match=f'Unknown key {INVALID}!'):
        Project.statistic_key_to_label(INVALID)


def _f_ics_date(dt: datetime):
    """Convert datetime objects to ics format."""
    return dt.strftime('%Y%m%dT%H%M%S')
