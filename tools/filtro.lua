-- Tablas de 1 columna (bloques de código de Google Docs) -> CodeBlock
local function inlines_to_text(inlines)
  local out = {}
  for _, i in ipairs(inlines) do
    if i.t == "Str" then
      table.insert(out, i.text)
    elseif i.t == "Space" then
      table.insert(out, " ")
    elseif i.t == "SoftBreak" or i.t == "LineBreak" then
      table.insert(out, "\n")
    else
      table.insert(out, pandoc.utils.stringify(i))
    end
  end
  return table.concat(out)
end

local function block_to_text(b)
  if b.t == "Para" or b.t == "Plain" then
    return inlines_to_text(b.content)
  elseif b.t == "CodeBlock" then
    return b.text
  else
    return pandoc.utils.stringify(b)
  end
end

function Table(tbl)
  if #tbl.colspecs ~= 1 then return nil end
  local lines = {}
  local function add_rows(rows)
    for _, row in ipairs(rows) do
      for _, cell in ipairs(row.cells) do
        for _, b in ipairs(cell.contents) do
          table.insert(lines, block_to_text(b))
        end
      end
    end
  end
  add_rows(tbl.head.rows)
  for _, body in ipairs(tbl.bodies) do add_rows(body.body) end
  local text = table.concat(lines, "\n")
  text = text:gsub("^%s+", ""):gsub("%s+$", "")
  return pandoc.CodeBlock(text, pandoc.Attr("", {"bash"}))
end

-- Encabezados vacíos (sin texto ni imagen) -> eliminar
function Header(el)
  if pandoc.utils.stringify(el.content):match("^%s*$") then
    for _, i in ipairs(el.content) do
      if i.t == "Image" or i.t == "RawInline" then return nil end
    end
    return {}
  end
end

-- Quitar portada + título + índice: todo lo anterior al primer apartado real
local INDICES = {
  ["ÍNDICE"] = true, ["INDICE"] = true,
  ["ÍNDICE DE CONTENIDOS"] = true,
  ["TABLA DE CONTENIDO"] = true, ["TABLA DE CONTENIDOS"] = true,
}

function Pandoc(doc)
  local blocks = doc.blocks
  local idx
  for i = 1, math.min(#blocks, 15) do
    local txt = pandoc.text.upper(pandoc.utils.stringify(blocks[i]))
    txt = txt:gsub("^%s+", ""):gsub("%s+$", "")
    if INDICES[txt] then idx = i; break end
  end
  if not idx then return nil end

  local first
  for j = idx + 1, #blocks do
    if blocks[j].t == "Header" then first = j; break end
  end
  if not first then return nil end

  local nuevo = pandoc.Blocks({})
  for j = first, #blocks do nuevo:insert(blocks[j]) end
  return pandoc.Pandoc(nuevo, doc.meta)
end
