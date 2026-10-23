# Checklist de homologação — LEFI 1.0

## Implementação conferida por inspeção estática

- [x] Novo módulo Django `lefi` e configurações separadas da Klaus.
- [x] Blueprint sugerido para novo serviço e novo banco PostgreSQL.
- [x] Logo enviada incorporada ao site e arquivos de identidade.
- [x] Vitrine editorial, categorias e filtros do catálogo, em português.
- [x] Páginas de produto, manifesto, ateliê e conteúdos comerciais revisados.
- [x] Dados das criações: materiais, procedência, intervenção, conservação, medidas e cápsulas.
- [x] Edição única 1/1 com verificações de estoque no cadastro e na compra.
- [x] Gestão de pedidos e painéis mantidos da base Klaus v1.2.
- [x] Checkout e pedidos manuais desabilitados por padrão para evitar recebimentos não configurados.
- [x] Referência de transação trocada para `LEFI-{id}`.
- [x] Nenhum produto de exemplo criado para fingir estoque, vendas ou fotos reais.

## Executar antes de uma publicação comercial

- [ ] Instalar Django e dependências no ambiente de testes.
- [ ] `python manage.py check` sem erros.
- [ ] `python manage.py makemigrations --check --dry-run` sem migrações pendentes.
- [ ] `python manage.py test store` com todos os testes passando (e correções quando necessárias).
- [ ] Verificar layout em celular, tablet e desktop no navegador real.
- [ ] Testar fotos reais, tamanhos, estoque/peça única e busca de coleção.
- [ ] Validar login, CPF, carrinho, checkout e telas de erro.
- [ ] Configurar e auditar política de preço, frete, devoluções, emissão fiscal e LGPD.
- [ ] Obter credenciais de pagamento exclusivas LEFI e testar confirmação autenticada, webhook e estorno.
- [ ] Confirmar política de marcas de terceiros e propriedade intelectual para peças transformadas.
- [ ] Validar isolamento e backup do novo banco da LEFI e seu plano de restauração.
- [ ] Substituir as imagens editoriais por material fotográfico próprio quando produzido.
- [ ] Cadastrar produtos reais, estoque e dados comerciais antes de habilitar vendas.

**Status:** entrega de código preparada. Não confundir com implantação realizada, testes de integração aprovados ou produto pronto para receber pagamentos.
