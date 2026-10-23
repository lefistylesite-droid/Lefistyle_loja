from django import forms

class CheckoutForm(forms.Form):
    full_name = forms.CharField(label='Nome completo', max_length=150, min_length=3)
    email = forms.EmailField(label='E-mail', max_length=254)
    phone = forms.CharField(label='Telefone para contato', min_length=10, max_length=20)
    postal_code = forms.RegexField(label='CEP', regex=r'^\d{5}-?\d{3}$', max_length=9)
    street = forms.CharField(label='Rua / Avenida', max_length=160)
    number = forms.CharField(label='Número', max_length=20)
    complement = forms.CharField(label='Complemento (opcional)', max_length=140, required=False)
    reference = forms.CharField(label='Referência para entrega (opcional)', max_length=200, required=False)
    neighborhood = forms.CharField(label='Bairro', max_length=100)
    city = forms.CharField(label='Cidade', max_length=100)
    state = forms.ChoiceField(label='UF', choices=[(x, x) for x in 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split()])
    def cleaned_address(self):
        return '\n'.join([self.cleaned_data['street']+', '+self.cleaned_data['number'],
               self.cleaned_data.get('complement',''), self.cleaned_data['neighborhood'],
               self.cleaned_data['city']+' / '+self.cleaned_data['state'],
               'CEP: '+self.cleaned_data['postal_code']]).strip()
