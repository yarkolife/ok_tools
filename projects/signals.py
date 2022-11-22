from .models import Project
from .models import ProjectParticipant
from django.db.models.signals import m2m_changed


def update_age_and_gender(sender, instance: Project, pk_set, action, **kwargs):
    """Set projects age and gender depending on the added participant."""
    if action == 'pre_add':
        for pk in pk_set:
            participant: ProjectParticipant = ProjectParticipant.objects.get(
                id=pk)
            age = participant.age
            gender = participant.gender

            if age is None:
                label = 'not_given'
            elif age < 7:
                label = '0_bis_6'
            elif age < 11:
                label = '7_bis_10'
            elif age < 15:
                label = '11_bis_14'
            elif age < 19:
                label = '15_bis_18'
            elif age < 35:
                label = '19_bis_34'
            elif age < 51:
                label = '35_bis_50'
            elif age < 66:
                label = '51_bis_65'
            else:
                label = 'ueber_65'

            match gender:
                case 'none':
                    index = 3
                case 'm':
                    index = 0
                case 'f':
                    index = 1
                case 'd':
                    index = 2
                case _:
                    raise ValueError(f'Unknown gender {gender}')

            instance.statistic.get(label)[index] += 1
            instance.save()


m2m_changed.connect(update_age_and_gender, sender=Project.participants.through)
