-- A small, built-in dark theme. Terminal colors have a 256-color fallback.
vim.cmd('highlight clear')
vim.o.background = 'dark'
vim.g.colors_name = 'workspace'
local c = {
  bg = { '#282c34', 236 }, fg = { '#abb2bf', 145 }, dim = { '#7f848e', 102 },
  panel = { '#353b45', 237 }, blue = { '#61afef', 75 }, cyan = { '#56b6c2', 80 },
  green = { '#98c379', 114 }, red = { '#e06c75', 168 }, gold = { '#e5c07b', 180 },
  purple = { '#c678dd', 176 },
}
local function hl(group, foreground, background, style)
  local spec = style or {}
  if foreground then spec.fg = c[foreground][1]; spec.ctermfg = c[foreground][2] end
  if background then spec.bg = c[background][1]; spec.ctermbg = c[background][2] end
  vim.api.nvim_set_hl(0, group, spec)
end
hl('Normal', 'fg', 'bg')
hl('NormalFloat', 'fg', 'panel')
hl('FloatBorder', 'cyan', 'panel')
hl('Comment', 'dim')
hl('Constant', 'gold')
hl('String', 'green')
hl('Identifier', 'red')
hl('Function', 'blue')
hl('Statement', 'purple')
hl('PreProc', 'gold')
hl('Type', 'cyan')
hl('Special', 'blue')
hl('Delimiter', 'fg')
hl('LineNr', 'dim')
hl('CursorLineNr', 'gold', nil, { bold = true })
hl('CursorLine', nil, 'panel')
hl('Visual', nil, 'panel')
hl('Search', 'bg', 'gold')
hl('IncSearch', 'bg', 'cyan')
hl('Pmenu', 'fg', 'panel')
hl('PmenuSel', 'bg', 'blue')
hl('StatusLine', 'bg', 'cyan', { bold = true })
hl('StatusLineNC', 'dim', 'panel')
hl('WinSeparator', 'dim')
hl('Directory', 'blue')
hl('Title', 'blue', nil, { bold = true })
hl('DiagnosticError', 'red')
hl('DiagnosticWarn', 'gold')
hl('DiagnosticInfo', 'blue')
hl('DiagnosticHint', 'cyan')
hl('ErrorMsg', 'red')
hl('WarningMsg', 'gold')
hl('DiffAdd', 'green', 'panel')
hl('DiffChange', 'gold', 'panel')
hl('DiffDelete', 'red', 'panel')
