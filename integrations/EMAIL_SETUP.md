# Notificações LEFI — Gmail Apps Script opcional

**Desativadas por padrão.** Esta entrega coloca os eventos e registros no PostgreSQL; para ENVIO REAL é necessário configurar o Gmail Apps Script, dar permissões e executar um teste com um pedido controlado. O Gmail/Apps Script possui limites e restrições próprios; não é infraestrutura de e-mails de alta disponibilidade.

1. Crie Gmail exclusivo da loja e acesse https://script.google.com. Crie novo projeto.
2. Cole `GmailAppsScript.gs`, vá a **Project Settings > Script properties**, configure `MAIL_SECRET` como token longo aleatório (não compartilhe).
3. Faça **Deploy > New deployment > Web app**, execute como **Você**, acesso **Anyone**. Esta permissão permite receber as requisições da LEFI, mas não dá acesso à sua caixa postal: o segredo na requisição deve ser mantido privado. Nunca coloque sua URL ou segredo no GitHub.
4. Copie a URL final que começa com `https://script.google.com/macros/s/.../exec`.
5. No Render, configure `LEFI_MAIL_SCRIPT_URL` com essa URL, `LEFI_MAIL_SCRIPT_SECRET` com o mesmo segredo das propriedades do Apps Script e `LEFI_EMAIL_ENABLED=1` **somente após testar com e-mail seu**.
6. Ações geram registros em **Admin > Notificações de e-mail**, com estado pendente / enviado / falha. Caso o serviço falhe, selecione notificações e use **Tentar enviar**. Nenhuma mensagem informa aprovação de pagamento sem validação pela InfinitePay.

> Observação: não há worker em segundo plano no plano gratuito Render. Há tentativa imediata após a transação, com falhas armazenadas; o reenvio posterior é **manual** no Admin. Não afirmar entrega garantida. Verifique os limites diários de MailApp.

**Sem as 3 variáveis:** os pedidos continuam sendo registrados normalmente, e os e-mails ficam apenas pendentes no banco. O checkout não depende do Gmail.
