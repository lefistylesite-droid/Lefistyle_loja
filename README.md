# LEFI — E-commerce de moda autoral e cultura de rua

**Versão entregue:** LEFI 1.0 · base Django da Klaus Pet v1.2 adaptada para uma operação **nova e independente**, com estética streetwear sofisticada e conteúdos públicos em português do Brasil.

A LEFI nasce para apresentar peças reconstruídas, roupas de segunda mão transformadas por intervenções artísticas, criações autorais, acessórios e objetos. O site foi estruturado para destacar **a peça, o processo, a identidade e a comunidade**, sem fingir vendas ou usar catálogo artificial.

## O que está de fato implementado

- Site público responsivo, identidade preta/grafite/off-white, logo oficial enviada, vitrine editorial de abertura, categorias, coleções e catálogo filtrável.
- Páginas «Nossa história» e «O ateliê», com narrativa comercial **em português** e imagens editoriais conceituais identificadas como tal.
- Fotos **reais de produtos** cadastráveis no painel; nenhum exemplo ilustrativo é publicado para compra. Se não houver fotos, aparece um quadro neutro.
- Modelagem de moda: coleção/cápsula, tipo de criação, exemplar 1/1, materiais, descrição da intervenção, procedência, condição, medidas, conservação, tamanhos do PP ao XG e numerações 34–48.
- Carrinho de compras com sessão e validação de estoque, cadastro com validação matemática de CPF e e-mail único, login, pedidos, painel, registro logístico e histórico operacional herdados da base 1.2.
- Checkout InfinitePay **preservado em código, mas desligado**, sem compartilhar a conta da Klaus; só ativar após credenciais **exclusivas da LEFI**, definição de frete, testes e avaliação de segurança.
- Proteção de estoque para edição única 1/1, com verificação ao salvar variação, adicionar à sacola e confirmar o pedido.
- URLs permanentes em português: `/`, `/manifesto/`, `/atelie/`, `/produto/`, `/carrinho/`, `/cadastro/`, `/minha-conta/`, `/painel/`, `/painel/pedidos/`, `/admin/`.

## O que não foi feito ou não deve ser presumido

- **Não foi implantado no Render**, tampouco conectado a banco de produção.
- **Não foi homologado com Django em execução neste ambiente**: as dependências não puderam ser instaladas porque o acesso à rede está indisponível. Foram feitas verificações estáticas/compilação de Python, e há suíte de testes para rodar em máquina com dependências.
- Não há produtos reais cadastrados, clientes, vendas, preços, medidas ou fotos das peças: isso exige dados da marca. Os retratos editoriais ilustram **direção artística**, não uma mercadoria concreta.
- Frete automático, pagamento por conta comercial LEFI, e-mail transacional e publicação em domínio próprio dependem de configuração, autorização e validação. Não afirmar que estão ativos.
- O projeto NÃO certifica autenticidade de roupas ou marcas de terceiros. Uso de tecidos ou peças antigas, quando existente, deve ser documentado honestamente, sem insinuar colaboração comercial com marcas originais.

## Estrutura técnica

- `lefi/settings.py` e `lefi/urls.py` — aplicação Django independente.
- `store/models.py` — catálogo, variações, fotos, pedidos e eventos.
- `store/migrations/0012_lefi_moda_autoral.py` — evolução aditiva e configuração das categorias de moda. As migrações antigas ficam presentes para reconstrução ordenada do esquema.
- `store/views.py` — vitrine, filtros, carrinho e compra.
- `store/infinitepay.py` — integração preservada, com referência única `LEFI-{pedido}`.
- `store/operations.py` e `templates/store/operations` — pedidos e operações.
- `templates/store/home.html`, `product.html`, `manifesto.html`, `atelie.html` — nova experiência.
- `static/css/lefi.css`, `static/img/logo-oficial-lefi.png`, `static/img/editorial-*.webp` — identidade e imagens editoriais.
- `render.yaml` — blueprint sugerido para **lefi-loja + lefi-db novos**, não utiliza serviço nem banco da Klaus.

## Testar no Windows localmente

**Caminho mais simples:** extraia o ZIP e dê dois cliques em `INICIAR_LEFI_WINDOWS.bat` (é necessário Python 3.12 e acesso à internet para obter as dependências). O iniciador cria ambiente isolado, executa migrações e abre o servidor **apenas no seu computador**. Para criar a conta administrativa, use o comando `createsuperuser` no terminal.

**Alternativa manual:**

Requisitos: Python 3.12 (recomendado), pip e ambiente virtual.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DEBUG='1'
$env:SECRET_KEY='somente-local-uma-chave-qualquer-para-desenvolvimento'
python manage.py migrate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test store --verbosity 2
python manage.py createsuperuser
python manage.py runserver
```

Abra `http://127.0.0.1:8000/` para ver a vitrine. O painel fica em `http://127.0.0.1:8000/painel/` (superusuário) e o cadastro em `/admin/`.

No PowerShell, caso a ativação do ambiente virtual esteja bloqueada, execute os comandos diretamente com `\.venv\Scripts\python.exe` em vez de alterar permanentemente a política de segurança.

## Cadastrar a primeira peça no painel

1. Acesse `/admin/`, «Produtos» → «Adicionar produto».
2. Escolha a categoria, coloque o nome real da peça e o identificador/slug.
3. Cadastre descrição, preço, custo (se usado), cápsula, materiais, processo criativo, procedência, condição, medidas e cuidados.
4. Assinale **Peça única 1/1** somente quando houver de fato uma única unidade. Registre as variações de tamanho, cor/acabamento, estoque e SKU distintos.
5. Adicione **fotos reais da peça**, como frente, costas, detalhes, textura, assinatura, etiqueta e marcas de uso. A galeria aceita múltiplas imagens.
6. Confirme tudo antes de marcar «Ativo» e «Destaque». O produto aparece na loja automaticamente.

**Sugestão para uma ficha real:** título «Jaqueta reconstruída — [nome da criação]», composição documentada, detalhes de costura e medidas em centímetros. Não atribua certificação, parceria, procedência ou autenticidade de marca sem documentação.

## Publicação independente no Render

1. Crie repositório **novo** `lefi-loja`; não use o repositório da Klaus. Envie o conteúdo do ZIP para a raiz dele.
2. Crie Blueprint a partir do `render.yaml` ou serviço web e banco PostgreSQL novos. Verifique o plano disponível no Render.
3. Confirme que o `DATABASE_URL` aponta **apenas ao banco da LEFI**; nunca copie URL de outro projeto, clientes ou credenciais do gateway.
4. Configure `SECRET_KEY`, `DEBUG=0`, domínio e hosts (variáveis seguras). Revise o arquivo `.env.example`.
5. Mantenha `LEFI_CHECKOUT_ENABLED=0`, `LEFI_ACCEPT_MANUAL_ORDERS=0` e `LEFI_EMAIL_ENABLED=0` até a homologação. Defina `LEFI_SHIPPING_FLAT` apenas se usar frete fixo real; não apresente como cotação de Correios.
6. Rode migrações, `check`, testes Django e uma compra controlada (sem cobrança real inicial). Cadastre contatos e políticas comerciais verificáveis.
7. Verifique homepage, cadastro, variações, fotos, carrinho, pedido, banco e painel. Só então considere liberar pagamentos.

**Segurança:** não publique `.env`, senhas, chaves ou URLs privadas. Não confunda imagens de conceito com fotos dos produtos vendidos. A LEFI não é afiliada a marcas de terceiros por usar peças reinterpretadas.

Leia também `CHECKLIST_LEFI.md` e `DIRECAO_CRIATIVA.md`.
