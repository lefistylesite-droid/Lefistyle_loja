# LEFI — CORREÇÃO DA VITRINE v1.1

## Problema relatado

O painel administrativo e páginas individuais de produtos abrem normalmente, mas a página inicial e a navegação de Loja, Categorias e Pesquisa resultam em HTTP 500 quando há produtos reais cadastrados. O teste com uma categoria inexistente abre normalmente.

## Alterações aplicadas ao código

- Os cartões de produto da vitrine usam dicionários preparados com campos selecionados do banco, em vez de carregar todos os modelos e relacionamentos na listagem.
- A imagem de capa é encontrada somente pelos metadados da galeria. A coluna binária `photo_data` **não é carregada** na consulta da listagem.
- Paginação de 24 produtos por página, com manutenção dos filtros.
- Cálculo de preço promocional seguro no Python (`has_discount`) em vez de lógica repetida no template.
- `collections` ordenadas pelo nome antes de aplicar `distinct()`, evitando ordenação implícita indesejada.
- Endereços próprios para `/loja/`, `/categorias/` e `/buscar/`; os menus e a lupa apontam para essas páginas.
- Se ocorrer uma nova falha na listagem, o `store.views` passa a registrar o traceback completo nos logs internos do servidor, sem registrar termos digitados, senhas ou dados de clientes.
- Testes de regressão para homepage, loja, categorias, busca, foto enviada, promoção e paginação.

## Segurança dos dados

Nenhuma migração nova. Nenhuma mudança no PostgreSQL, no checkout, no painel administrativo, nos modelos, nos uploads ou nas credenciais. **Não apague nem recrie banco, fotos ou produtos.**

## Como atualizar GitHub / Render

1. Faça backup do banco atual da LEFI, conforme os recursos disponíveis na sua conta Render.
2. No repositório `lefi-loja`, mantenha os arquivos `render.yaml`, `manage.py` e `requirements.txt`.
3. Extraia este ZIP. Atualize os arquivos do repositório mantendo seus caminhos (por exemplo `store/views.py` na pasta `store`).
4. Faça um commit com mensagem `LEFI 1.1 - correção vitrine e busca`.
5. O Render ligado ao repositório deverá implantar o novo commit automaticamente, se o autodeploy estiver ligado. Caso contrário, use **Manual Deploy > Deploy latest commit**.
6. Teste nesta ordem: `/health/`, `/`, `/loja/`, `/categorias/`, `/buscar/?q=bone`, `/loja/?categoria=acessorios`, uma página `/produto/<slug>/` e `/admin/`.
7. Faça uma busca pelo nome real de uma peça cadastrada para verificar que aparecem capa, preço e link do produto.

Se a página continuar com HTTP 500: vá em **Render > lefi-loja > Logs**, procure `Falha ao renderizar vitrine LEFI` e copie o `Traceback` até a última linha (ocultando eventuais valores sensíveis). Aí teremos a causa concreta do ambiente de produção.

## Validação realizada

- Revisão do código-fonte do ZIP LEFI 1.0 disponibilizado no chat.
- Sintaxe Python examinada (`ast.parse`) nos arquivos de código.
- Verificação de novos endereços, inclusões, templates e arquivos compactados.
- Testes Django de regressão foram **escritos, mas não executados** neste ambiente: a instalação do Django não está disponível e a rede do ambiente não permite baixar as dependências.

A correção ataca a área apontada pelos testes do usuário. Sem o traceback da produção, não é possível garantir que a causa raiz seja exclusivamente a consulta ou o processamento dos cartões. Não a classifique como homologada até os testes no Render.

## Retorno à versão anterior (rollback)

Caso apareça um problema novo, no GitHub reverta o commit desta atualização ou, no Render, retorne à última implantação estável. Não modifique o banco durante a reversão, pois esta atualização não cria migração.
