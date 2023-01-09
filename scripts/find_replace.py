from licenses.models import License


def run():
    """
    Implement a find and replace tool for Licenses.

    Considers the fields 'title', 'subtitle' and 'description'.
    """
    FIND = '_x000d_'
    REPLACE = ''

    queryset = License.objects.all()
    for lc in queryset:
        DESCRIPTION = lc.description and FIND in lc.description
        TITLE = lc.title and FIND in lc.title
        SUBTITLE = lc.subtitle and FIND in lc.subtitle

        if not (DESCRIPTION or TITLE or SUBTITLE):
            continue

        CONFIRMED = lc.confirmed

        if CONFIRMED:
            # If the license is already confirmed we need to unconfirm them
            # before we can make our changes.
            lc.confirmed = False
            lc.save(update_fields=['confirmed'])

        if DESCRIPTION:
            lc.description = lc.description.replace(FIND, REPLACE)
        if TITLE:
            lc.title = lc.title.replace(FIND, REPLACE)
        if SUBTITLE:
            lc.subtitle = lc.subtitle.replace(FIND, REPLACE)

        lc.confirmed = CONFIRMED
        lc.save()
