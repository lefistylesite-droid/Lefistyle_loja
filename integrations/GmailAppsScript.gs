/**
 * LEFI — ponte opcional de e-mails transacionais Gmail (Apps Script).
 * Código para projeto próprio em script.google.com, não coloque segredo aqui.
 * Defina MAIL_SECRET em Project Settings > Script Properties.
 * Implantar como Web App: executar como proprietário, acesso "qualquer pessoa".
 * O segredo aleatório é obrigatório e deve ser mantido privado no Render.
 * A API é pública para chamadas; proteja a URL e mantenha o segredo confidencial.
 */
function doPost(e) {
  try {
    const data = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    const expected = PropertiesService.getScriptProperties().getProperty('MAIL_SECRET');
    if (!expected || !data.secret || data.secret !== expected) {
      return ContentService.createTextOutput(JSON.stringify({ok:false})).setMimeType(ContentService.MimeType.JSON);
    }
    if (!data.to || !data.subject || !data.html || !/^\S+@\S+\.\S+$/.test(data.to)) {
      return ContentService.createTextOutput(JSON.stringify({ok:false})).setMimeType(ContentService.MimeType.JSON);
    }
    // Nenhum envio de campanhas. Apenas avisos individuais dos pedidos.
    MailApp.sendEmail({to: data.to, subject: data.subject, body: 'Notificação de pedido LEFI.', htmlBody: data.html, name:'LEFI | Pedidos'});
    return ContentService.createTextOutput(JSON.stringify({ok:true})).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ok:false})).setMimeType(ContentService.MimeType.JSON);
  }
}
