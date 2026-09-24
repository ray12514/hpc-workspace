vim.g.mapleader = ' '
vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.expandtab = true
vim.opt.shiftwidth = 4
vim.opt.tabstop = 4
vim.opt.ignorecase = true
vim.opt.smartcase = true
local color = vim.env.WS_COLOR or 'auto'
local no_color = color == 'never' or vim.env.NO_COLOR ~= nil or vim.env.TERM == 'dumb'
vim.opt.termguicolors = not no_color and (color == 'truecolor' or
  (color == 'auto' and (vim.env.COLORTERM == 'truecolor' or vim.env.COLORTERM == '24bit')))
if not no_color then
  local colors = tonumber(vim.fn.systemlist({ 'tput', 'colors' })[1]) or 0
  if vim.o.termguicolors or color == '256' or colors >= 256 then
    vim.cmd.colorscheme('workspace')
  end
end
vim.opt.splitright = true
vim.opt.splitbelow = true
vim.opt.undofile = true
vim.opt.signcolumn = 'yes'
vim.opt.updatetime = 300
vim.opt.autoread = true
vim.api.nvim_create_autocmd({ 'FocusGained', 'BufEnter', 'CursorHold' }, {
  callback = function()
    if vim.fn.mode() ~= 'c' then vim.cmd('silent! checktime') end
  end,
})
vim.opt.sessionoptions = 'buffers,curdir,folds,help,tabpages,winsize'
local root = vim.fn.stdpath('state')
vim.fn.mkdir(root .. '/undo', 'p')
vim.opt.undodir = root .. '/undo//'
local session = root .. '/sessions/' .. vim.fn.sha256(vim.fn.getcwd()):sub(1, 20) .. '.vim'
local function save_session()
  vim.fn.mkdir(root .. '/sessions', 'p')
  vim.cmd('silent! mksession! ' .. vim.fn.fnameescape(session))
end
local function restore_session()
  if vim.fn.filereadable(session) == 1 then
    vim.cmd('silent! source ' .. vim.fn.fnameescape(session))
  end
end
vim.api.nvim_create_user_command('WorkspaceSave', save_session, {})
vim.api.nvim_create_user_command('WorkspaceRestore', restore_session, {})
vim.keymap.set('n', '<leader>ws', save_session, { desc = 'Save workspace layout' })
vim.keymap.set('n', '<leader>wr', restore_session, { desc = 'Restore workspace layout' })
vim.keymap.set('n', '<leader>e', '<cmd>Explore<cr>', { desc = 'Browse files' })
vim.api.nvim_create_autocmd('VimLeavePre', { callback = save_session })
vim.api.nvim_create_autocmd('VimEnter', {
  callback = function()
    if vim.fn.argc() == 0 and #vim.api.nvim_list_uis() > 0 then restore_session() end
  end,
})
if vim.fn.executable('clangd') == 1 then
  vim.lsp.config('clangd', {
    cmd = { 'clangd' }, filetypes = { 'c', 'cpp', 'objc', 'objcpp' },
    root_markers = { '.clangd', 'compile_commands.json', '.git' },
  })
  vim.lsp.enable('clangd')
end
if vim.env.WS_LAYOUT == 'thin-v1' and vim.fn.isdirectory('/workspace-tools/share/nvim') == 1 then
  require('workspace.editor').setup()
end
local custom = vim.env.HOME .. '/.config/hpc-workspace/nvim.lua'
if vim.fn.filereadable(custom) == 1 then dofile(custom) end
