from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.http import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _


def accessibility_statement(request):
    """Page for the accessibility statement."""
    return render(request, 'accessibility_statement.html')


def accessibility_feedback(request):
    """Page for accessibility feedback."""
    if request.method == 'POST':
        # Processing the feedback form
        name = request.POST.get('name', '')
        email = request.POST.get('email', '')
        url = request.POST.get('url', '')
        barrier_type = request.POST.get('barrier_type', '')
        description = request.POST.get('description', '')
        assistive_tech = request.POST.get('assistive_tech', '')

        # Validation
        if not url or not barrier_type or not description:
            messages.error(request, _('Please fill in all required fields.'))
            return render(request, 'accessibility_feedback.html')

        # Send email
        subject = _('Accessibility barrier reported: {barrier_type}').format(barrier_type=barrier_type)
        message = f"""
        Name: {name}
        Email: {email}
        Affected page: {url}
        Type of barrier: {barrier_type}
        Assistive technology: {assistive_tech}

        Description:
        {description}
        """

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                ['accessibility@example.com'],
                fail_silently=False,
            )
            messages.success(request, _('Thank you for your message. We will contact you within 2 weeks.'))
            return redirect('accessibility_feedback')
        except Exception as e:
            messages.error(request, _('There was an error sending your message. Please try again later.'))

    return render(request, 'accessibility_feedback.html')
