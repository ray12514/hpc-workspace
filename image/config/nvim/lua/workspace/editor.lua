local M = {}

function M.setup()
  -- Native read-only packages, installed with the image. No startup installer.
  vim.g.tmux_navigator_no_mappings = 1
  vim.g.tmux_navigator_no_wrap = 1
  vim.cmd.packloadall()

  local border = { '+', '-', '+', '|', '+', '-', '+', '|' }
  local fzf = require('fzf-lua')
  fzf.setup({
    file_icons = false, git_icons = false, color_icons = false,
    winopts = { border = border, preview = { border = border } },
    fzf_opts = { ['--pointer'] = '>', ['--marker'] = '+', ['--separator'] = '-' },
  })
  fzf.register_ui_select()
  require('which-key').setup({
    preset = 'classic', win = { border = border },
    icons = {
      mappings = false, breadcrumb = '>', separator = ':', group = '+', ellipsis = '...',
      keys = { Up = 'Up', Down = 'Down', Left = 'Left', Right = 'Right',
        C = 'Ctrl-', M = 'Alt-', D = 'Super-', S = 'Shift-', CR = 'Enter', Esc = 'Esc',
        Space = 'Space', Tab = 'Tab', BS = 'Backspace', Del = 'Delete',
        NL = 'Enter', F1 = 'F1', F2 = 'F2', F3 = 'F3', F4 = 'F4',
        F5 = 'F5', F6 = 'F6', F7 = 'F7', F8 = 'F8', F9 = 'F9',
        F10 = 'F10', F11 = 'F11', F12 = 'F12' },
    },
  })
  require('which-key').add({
    { '<leader>f', group = 'find' }, { '<leader>c', group = 'code' },
    { '<leader>g', group = 'git' }, { '<leader>w', group = 'workspace / windows' },
  })
  local signs = { add = { text = '+' }, change = { text = '~' }, delete = { text = '-' },
    topdelete = { text = '-' }, changedelete = { text = '~' }, untracked = { text = '?' } }
  local git = require('gitsigns')
  git.setup({ signs = signs, signs_staged = signs, current_line_blame = false,
    max_file_length = 20000, update_debounce = 250 })

  local blink = require('blink.cmp')
  blink.setup({
    fuzzy = { implementation = 'lua' },
    keymap = { preset = 'none', ['<C-n>'] = { 'select_next', 'fallback' },
      ['<C-p>'] = { 'select_prev', 'fallback' }, ['<C-y>'] = { 'accept', 'fallback' },
      ['<C-e>'] = { 'hide', 'fallback' }, ['<C-Space>'] = { 'show', 'show_documentation', 'hide_documentation' } },
    completion = {
      list = { selection = { preselect = false, auto_insert = false } },
      menu = { border = border, draw = { columns = { { 'label', 'label_description', gap = 1 }, { 'kind' } } } },
      documentation = { auto_show = false, window = { border = border } },
    },
    sources = { default = { 'lsp', 'path', 'snippets', 'buffer' } },
    signature = { enabled = true, window = { border = border } },
  })

  local conform = require('conform')
  conform.setup({
    formatters_by_ft = { python = { 'ruff_format' }, sh = { 'shfmt' },
      bash = { 'shfmt' }, c = { 'clang_format' }, cpp = { 'clang_format' } },
    -- Formatting is a deliberate action. Site clang-format is used if present.
    default_format_opts = { timeout_ms = 3000, lsp_format = 'fallback' },
  })

  local map = function(key, action, description)
    vim.keymap.set('n', '<leader>' .. key, action, { desc = description })
  end
  map('ff', fzf.files, 'Find project files')
  map('fg', fzf.live_grep, 'Search project text')
  map('fb', fzf.buffers, 'Switch buffer')
  map('fs', fzf.lsp_document_symbols, 'Find symbols')
  map('cd', fzf.diagnostics_document, 'Show diagnostics')
  map('ca', vim.lsp.buf.code_action, 'Code action')
  map('cr', vim.lsp.buf.rename, 'Rename symbol')
  map('cf', function() conform.format({ async = true }) end, 'Format buffer')
  map('gp', git.preview_hunk, 'Preview Git hunk')
  map('gs', git.stage_hunk, 'Stage Git hunk')
  map('?', function() require('which-key').show({ global = true }) end, 'Shortcut help')
  for key, direction in pairs({ h = 'Left', j = 'Down', k = 'Up', l = 'Right' }) do
    map('w' .. key, '<cmd>TmuxNavigate' .. direction .. '<cr>', 'Move ' .. direction:lower() .. ' across editor/tmux panes')
  end
  vim.keymap.set('n', 'gd', vim.lsp.buf.definition, { desc = 'Go to definition' })
  vim.keymap.set('n', 'grr', fzf.lsp_references, { desc = 'Find references' })
  vim.diagnostic.config({ virtual_text = false, severity_sort = true,
    float = { border = border }, signs = { text = { 'E', 'W', 'I', 'H' } } })

  local function small_buffer(buf)
    local stat = vim.uv.fs_stat(vim.api.nvim_buf_get_name(buf))
    return (not stat or stat.size <= 1024 * 1024) and vim.api.nvim_buf_line_count(buf) <= 20000
  end
  vim.api.nvim_create_autocmd('FileType', {
    callback = function(event)
      if small_buffer(event.buf) then
        -- Missing parsers retain native syntax. Nothing is downloaded/compiled.
        pcall(vim.treesitter.start, event.buf)
      end
    end,
  })

  local function server(name, options)
    if vim.fn.executable(options.cmd[1]) ~= 1 then return end
    options.capabilities = blink.get_lsp_capabilities()
    local markers = options.root_markers
    options.root_dir = function(bufnr, on_dir)
      if small_buffer(bufnr) then on_dir(vim.fs.root(bufnr, markers) or vim.fn.getcwd()) end
    end
    vim.lsp.config(name, options)
    vim.lsp.enable(name)
  end
  server('clangd', { cmd = { 'clangd', '--background-index=0' },
    filetypes = { 'c', 'cpp', 'objc', 'objcpp' }, root_markers = { '.clangd', 'compile_commands.json', '.git' } })
  server('fortls', { cmd = { 'fortls', '--disable_autoupdate', '--nthreads', '1' },
    filetypes = { 'fortran' }, root_markers = { '.fortls', '.git' },
    settings = {} })
  server('basedpyright', { cmd = { 'basedpyright-langserver', '--stdio' },
    filetypes = { 'python' }, root_markers = { 'pyrightconfig.json', 'pyproject.toml', '.git' },
    settings = { python = { pythonPath = vim.env.VIRTUAL_ENV and (vim.env.VIRTUAL_ENV .. '/bin/python') or vim.fn.exepath('python3') },
      basedpyright = { analysis = { diagnosticMode = 'openFilesOnly', autoSearchPaths = false,
        typeCheckingMode = 'standard', exclude = { '**/.git', '**/.venv', '**/build', '**/dist' } } } } })
  server('ruff', { cmd = { 'ruff', 'server' }, filetypes = { 'python' },
    root_markers = { 'ruff.toml', '.ruff.toml', 'pyproject.toml', '.git' },
    on_attach = function(client) client.server_capabilities.hoverProvider = false end })
  server('bashls', { cmd = { 'bash-language-server', 'start' }, filetypes = { 'sh', 'bash' },
    root_markers = { '.git', '.shellcheckrc' },
    settings = { bashIde = { explainshellEndpoint = '', backgroundAnalysisMaxFiles = 100,
      globPattern = '**/*@(.sh|.inc|.bash|.command)', shellcheckPath = 'shellcheck' } } })
end

return M
