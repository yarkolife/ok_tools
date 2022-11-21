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
                instance.tn_age_not_given += 1
            elif age < 7:
                instance.tn_0_bis_6 += 1
            elif age < 11:
                instance.tn_7_bis_10 += 1
            elif age < 15:
                instance.tn_11_bis_14 += 1
            elif age < 19:
                instance.tn_15_bis_18 += 1
            elif age < 35:
                instance.tn_19_bis_34 += 1
            elif age < 51:
                instance.tn_35_bis_50 += 1
            elif age < 66:
                instance.tn_51_bis_65 += 1
            else:
                instance.tn_ueber_65 += 1

            match gender:
                case None:
                    instance.tn_gender_not_given += 1
                case 'm':
                    instance.tn_male += 1
                case 'f':
                    instance.tn_female += 1
                case 'd':
                    instance.tn_diverse += 1

            instance.save()
            pass


m2m_changed.connect(update_age_and_gender, sender=Project.participants.through)
