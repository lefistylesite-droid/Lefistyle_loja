"""Upload de fotos reais no painel, sem depender do filesystem efêmero do Render Free.
As imagens convertidas ficam no PostgreSQL para a versão de testes.
"""
from io import BytesIO
from django import forms
from PIL import Image, ImageOps, UnidentifiedImageError
from .models import ProductImage

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_SAVED_BYTES = 900 * 1024
ACCEPTED_FORMATS = {'JPEG', 'PNG', 'WEBP'}

class ProductPhotoForm(forms.ModelForm):
    upload = forms.ImageField(
        label='Selecionar foto do computador/celular', required=False,
        help_text='JPG, PNG ou WebP até 5 MB. Convertida automaticamente para WebP. A menor posição vira a capa.',
        widget=forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
    )
    class Meta:
        model = ProductImage
        fields = ('upload', 'alt', 'position')

    def clean_upload(self):
        upload = self.cleaned_data.get('upload')
        self._optimized_photo = None
        if not upload:
            return upload
        if upload.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError('Escolha uma foto com até 5 MB.')
        try:
            upload.seek(0)
            with Image.open(upload) as original:
                if original.format not in ACCEPTED_FORMATS:
                    raise ValueError('Formato não permitido')
                if original.width * original.height > 24_000_000:
                    raise ValueError('Imagem com dimensões grandes demais')
                img = ImageOps.exif_transpose(original)
                img.thumbnail((1400, 1400))
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGB')
                if img.mode == 'RGBA':
                    canvas = Image.new('RGB', img.size, '#fffaf5')
                    canvas.paste(img, mask=img.getchannel('A'))
                    img = canvas
                payload = None
                for quality in (83, 72, 60, 48):
                    buffer = BytesIO()
                    img.save(buffer, format='WEBP', quality=quality, method=4)
                    payload = buffer.getvalue()
                    if len(payload) <= MAX_SAVED_BYTES:
                        break
                if len(payload) > MAX_SAVED_BYTES:
                    raise ValueError('Foto muito complexa; reduza resolução ou tamanho')
                self._optimized_photo = payload
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
            raise forms.ValidationError(f'Não foi possível processar a foto: {exc}') from exc
        return upload

    def clean(self):
        data = super().clean()
        if (not self.instance.pk and self.has_changed() and
                not data.get('upload')):
            self.add_error('upload', 'Envie uma foto para esta linha da galeria.')
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self._optimized_photo is not None:
            obj.photo_data = self._optimized_photo
            obj.has_upload = True
            obj.image_url = ''
        if commit:
            obj.save()
            self.save_m2m()
        return obj
