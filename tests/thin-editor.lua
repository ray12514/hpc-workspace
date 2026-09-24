local ok, err = xpcall(function()
  assert(vim.g.fixture_custom == 123, 'Personal editor override was not loaded')
  for _, name in ipairs({ 'fzf-lua', 'which-key', 'gitsigns', 'blink.cmp', 'conform' }) do
    assert(require(name), 'Missing plugin ' .. name)
  end
  assert(vim.fn.exists(':TmuxNavigateLeft') == 2)
  local examples = {
    c = 'int main(void) { return 0; }', cpp = 'int main() { return 0; }',
    fortran = 'program main\nend program main', python = 'x = 1', bash = 'echo hello',
    json = '{"x":1}', yaml = 'x: 1', lua = 'local x = 1', markdown = '# hello',
    markdown_inline = 'hello **world**', cmake = 'project(example)', vim = 'set number', vimdoc = '*help*',
  }
  for language, source in pairs(examples) do
    local parser = vim.treesitter.get_string_parser(source, language)
    assert(parser:parse()[1], 'Cannot parse ' .. language)
    assert(vim.treesitter.query.get(language, 'highlights'), 'Missing highlight queries: ' .. language)
  end

  local file = vim.fn.getcwd() .. '/editor-fixture.py'
  vim.fn.writefile({ 'value: int = "wrong"', 'print(value)' }, file)
  vim.cmd.edit(vim.fn.fnameescape(file))
  assert(vim.wait(30000, function()
    return #vim.lsp.get_clients({ name = 'basedpyright', bufnr = 0 }) == 1
      and #vim.diagnostic.get(0) > 0
  end, 100), 'Python language server did not publish actual diagnostics')
  local client = vim.lsp.get_clients({ name = 'basedpyright', bufnr = 0 })[1]
  local completion = client:request_sync('textDocument/completion', {
    textDocument = { uri = vim.uri_from_bufnr(0) }, position = { line = 1, character = 3 },
  }, 10000, 0)
  assert(completion and completion.result, 'Completion request failed')
  assert(vim.treesitter.highlighter.active[vim.api.nvim_get_current_buf()], 'Treesitter did not start for Python')

  vim.api.nvim_buf_set_lines(0, 0, -1, false, { 'x=  [1,2,3]' })
  local formatted = false
  require('conform').format({ async = false, timeout_ms = 10000 }, function(format_error)
    assert(not format_error, tostring(format_error))
    formatted = true
  end)
  assert(formatted and vim.api.nvim_buf_get_lines(0, 0, 1, false)[1] == 'x = [1, 2, 3]', 'Manual Ruff formatting failed')
  vim.cmd.write()
  vim.fn.writefile({ 'external = 4' }, file)
  vim.cmd.checktime()
  assert(vim.api.nvim_buf_get_lines(0, 0, 1, false)[1] == 'external = 4', 'External edit did not reload')
  vim.api.nvim_buf_set_lines(0, 0, -1, false, { 'unsaved = 5' })
  vim.fn.writefile({ 'external = 6' }, file)
  -- Suppress the interactive conflict prompt for this automated assertion only.
  vim.api.nvim_create_autocmd('FileChangedShell', { once = true, callback = function() vim.v.fcs_choice = '' end })
  vim.cmd.checktime()
  assert(vim.bo.modified and vim.api.nvim_buf_get_lines(0, 0, 1, false)[1] == 'unsaved = 5', 'Unsaved edits were discarded')
  vim.bo.modified = false
  for _, example in ipairs({
    { 'editor-fixture.f90', 'fortls', { 'program fixture', 'implicit none', 'integer :: count', 'count = 1', 'end program fixture' } },
    { 'editor-fixture.sh', 'bashls', { '#!/bin/bash', 'fixture() { echo "$undefined"; }', 'fixture' } },
  }) do
    local path = vim.fn.getcwd() .. '/' .. example[1]
    vim.fn.writefile(example[3], path)
    vim.cmd.edit(vim.fn.fnameescape(path))
    assert(vim.wait(20000, function()
      local clients = vim.lsp.get_clients({ name = example[2], bufnr = 0 })
      return #clients == 1 and clients[1].initialized
    end, 100), 'Language server did not initialize: ' .. example[2])
    local lsp = vim.lsp.get_clients({ name = example[2], bufnr = 0 })[1]
    local symbols
    assert(vim.wait(15000, function()
      symbols = lsp:request_sync('textDocument/documentSymbol', { textDocument = { uri = vim.uri_from_bufnr(0) } }, 2000, 0)
      return symbols and symbols.result and #symbols.result > 0
    end, 200), 'No real symbols from ' .. example[2] .. ': ' .. vim.inspect(symbols))
  end
  vim.cmd.WorkspaceSave()
  print('editor-toolkit-passed')
end, debug.traceback)
if not ok then
  io.stderr:write(err .. '\n')
  vim.cmd('cquit 1')
else
  vim.cmd('qa!')
end
