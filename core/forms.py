from django import forms


class IssueSyncForm(forms.Form):
    STATE_CHOICES = [
        ('all', 'Todas'),
        ('open', 'Abertas'),
        ('closed', 'Fechadas'),
    ]
    state = forms.ChoiceField(
        choices=STATE_CHOICES,
        required=True,
        label='Estado',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    since_datetime = forms.DateTimeField(
        required=True,
        label='Desde',
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )
    full_sync = forms.BooleanField(
        required=False,
        label='Sincronização completa',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class CommitSyncForm(forms.Form):
    since_datetime = forms.DateTimeField(
        required=True,
        label='Desde',
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )
    until_datetime = forms.DateTimeField(
        required=True,
        label='Até',
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )
    full_sync = forms.BooleanField(
        required=False,
        label='Sincronização completa',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )