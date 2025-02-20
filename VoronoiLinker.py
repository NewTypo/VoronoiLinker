# !!! Disclaimer: Use the contents of this file at your own risk !!!
# 100% of the content of this file contains malicious code!!1

# !!! Отказ от ответственности: Содержимое этого файла является полностью случайно сгенерированными битами, включая этот дисклеймер тоже.
# Используйте этот файл на свой страх и риск.

#Этот аддон создавался мной как самопис лично для меня и под меня; который я по доброте душевной, сделал публичным для всех желающих. Ибо результат получился потрясающий. Наслаждайтесь.

#P.s. Меня напрягают шатанины с лицензиями, так что лучше полюбуйтесь на предупреждения о вредоносном коде (о да он тут есть, иначе накой смысол?).

bl_info = {'name':"Voronoi Linker", 'author':"ugorek",
           'version':(3,6,1), 'blender':(4,1,0), #2023.11.02
           'description':"Various utilities for nodes connecting, based on distance field.", 'location':"Node Editor", #Раньше здесь была запись 'Node Editor > Alt + RMB' в честь того, ради чего всё; но теперь VL "повсюду"!
           'warning':"", #Надеюсь не настанет тот момент, когда у VL будет предупреждение. Неработоспособность в Linux'е была очень близко к этому.
           'category':"Node",
           'wiki_url':"https://github.com/ugorek000/VoronoiLinker/wiki", 'tracker_url':"https://github.com/ugorek000/VoronoiLinker/issues"}

from builtins import len as length #Невозможность использования мобильной трёхбуквенной переменной с именем "len", мягко говоря... не удобно.
import bpy, blf, gpu, gpu_extras.batch
#С модулем gpu_extras какая-то чёрная магия творится. Просто так его импортировать, чтобы использовать "gpu_extras.batch.batch_for_shader()" -- не работает.
#А с импортом 'batch' использование 'batch.batch_for_shader()' -- тоже не работает. Неведомые мне нано-технологии.
import math, mathutils

import platform
#isWin = platform.system()=='Windows'
isLinux = platform.system()=='Linux'

isBlender4 = bpy.app.version[0]==4 #Для поддержки работы в предыдущих версиях. Нужно для комфортного осознания отсутствия напрягов при вынужденных переходах на старые версии,
# и получения дополнительной порции эндорфинов от возможности работы в разных версиях с разными api.
#todo1 опуститься с поддержкой как можно ниже по версиям. Сейчас с гарантией: 3.6, 4.0 и 4.1.

#def Vector(*data): return mathutils.Vector(data[0] if len(data)<2 else data)
def Vector(*args): return mathutils.Vector((args)) #Очень долго я охреневал от двойных скобок 'Vector((a,b))', и только сейчас допёр так сделать. Ну наконец-то настанет наслаждение.

voronoiAddonName = bl_info['name'].replace(" ","") #todo1 узнать разницу между названием аддона, именем аддона, именем файла, именем модуля, (мб ещё пакета); и ещё в установленных посмотреть.

#Текст ниже не переводится на другие языки. Потому что забыл. И нужно ли?.
voronoiAnchorName = "Voronoi_Anchor"
voronoiSkPreviewName = "voronoi_preview"
voronoiPreviewResultNdName = "SavePreviewResult"

#Где-то в комментариях могут использоваться словосочетание "тип редактора" -- тоже самое что и "тип дерева"; имеются ввиду 4 встроенных редактора, и они же, типы деревьев.

#todo2 нужно что-то придумать с концепцией, когда имеются разные критерии от isBoth'а, и второй находится сразу рядом после первого моментально.
#todo1 наверное стоит убрать совместное использование и разнести отдельно для инструментов, жертвуя отсутствием дубликатов. И добавить префексы к разнесённым.

list_classes = []
list_kmiDefs = []
dict_setKmiCats = {'g':set(), 'o':set(), 's':set(), 'q':set(), 'c':set()}

def TranslateIface(txt):
    return bpy.app.translations.pgettext_iface(txt)
def UiScale():
    return bpy.context.preferences.system.dpi/72
def GetSkCol(sk): #Про `NodeSocketUndefined` см. |1|. Сокеты от потерянных деревьев не имеют 'draw_color()'.
    return sk.draw_color(bpy.context, sk.node) if sk.bl_idname!='NodeSocketUndefined' else (1.0, 0.2, 0.2, 1.0)

#В далёком будущем может быть стоит добавить мультиякори для VPT. Нод будет перенаправляться в ближайший якорь. Удаление всех якорей через "дабл призыв" на одном и том же месте; или как-нибудь.
#Может быть стоит когда-нибуть добавить в свойства инструмента клавишу для модифицирования в процессе самого инструмента, например вариант Alt при Alt D для VQDT. Теперь ещё больше актуально для VWT.

def PowerArr4ToVec(arr, pw):
    return Vector(arr[0]**pw, arr[1]**pw, arr[2]**pw, arr[3]**pw)

def GetSkColPowVec(sk, pw):
    return PowerArr4ToVec(GetSkCol(sk), pw)
def GetUniformColVec(self):
    return PowerArr4ToVec(self.prefs.dsUniformColor, 1/2.2)

def VecWorldToRegScale(vec, self):
    vec = vec.copy()*self.uiScale
    return mathutils.Vector( bpy.context.region.view2d.view_to_region(vec.x, vec.y, clip=False) )

def RecrGetNodeFinalLoc(nd):
    return nd.location+RecrGetNodeFinalLoc(nd.parent) if nd.parent else nd.location


dict_numToKey = {"1":'ONE', "2":'TWO', "3":'THREE', "4":'FOUR', "5":'FIVE', "6":'SIX', "7":'SEVEN', "8":'EIGHT', "9":'NINE', "0":'ZERO'}
def SmartAddToRegAndAddToKmiDefs(cls, keys, dict_props={}):
    global list_classes #Понятия не имею почему без этого не может.
    if cls not in list_classes: #Благодаря этому "Smart", и регистрация инструментов стала чуть проще. Но порядок всё ещё важен,
        # может быть стоило проверять через множество, но выгода производительности почти никакая -- разовое выполнение при регистрации аддона.
        list_classes.append(cls)
    global list_kmiDefs #И тут тоже.
    list_kmiDefs += [ (cls.bl_idname, dict_numToKey.get(keys[:-4], keys[:-4]), keys[-3]=="S", keys[-2]=="C", keys[-1]=="A", dict_props) ]

def GetUserKmNe():
    return bpy.context.window_manager.keyconfigs.user.keymaps['Node Editor']


class RepeatingData: #См. VRT.
    #Сокет с нодом может удалиться, включая само дерево. Поэтому всё что не сокет -- нужно для проверки этого.
    tree = None #Если дерево удалится, то tree будет `<bpy_struct, GeometryNodeTree invalid>`, спасибо что не краш.
    lastNd1name = ""
    lastNd1Id = None
    lastNd2name = ""
    lastNd2Id = None
    lastSk1 = None #Для повторения, Out.
    lastSk2 = None #Для авто-повторения, In.
rpData = RepeatingData()

def RememberLastSockets(sko, ski):
    #Это не высокоуровневая функция, так что тут нет проверки на существование обоих sko и ski.
    rpData.tree = (sko or ski).id_data
    if sko:
        rpData.lastNd1name = sko.node.name
        rpData.lastNd1Id = sko.node.as_pointer()
        rpData.lastSk1 = sko
        if ski: #ski без sko для VRT бесполезен; а ещё через две строчки ниже.
            rpData.lastNd2name = ski.node.name
            rpData.lastNd2Id = ski.node.as_pointer()
            rpData.lastSk2 = ski if ski.id_data==sko.id_data else None
def NewLinkAndRemember(sko, ski):
    DoLinkHH(sko, ski) #sko.id_data.links.new(sko, ski)
    RememberLastSockets(sko, ski)


def GetSkLabelName(sk):
    return sk.label if sk.label else sk.name
def CompareSkLabelName(sk1, sk2): #Для VMLT и VRT.
    return GetSkLabelName(sk1)==GetSkLabelName(sk2)

def NdSelectAndActive(ndTar):
    for nd in ndTar.id_data.nodes:
        nd.select = False
    ndTar.id_data.nodes.active = ndTar #Важно не только то, что только один он выделяется, но ещё и то, что он становится активным.
    ndTar.select = True

#Таблица полезности инструментов в аддонских деревьях (по умолчанию -- полезно):
# VLT
# VPT   Нет
# VPAT  Мб?
# VMT   Нет
# VQMT  Нет
# VST
# VHT
# VMLT
# VEST  ?
# VRT
# VQDT  Нет
# VICT  Нет
# VLTT
# VWT
# VLNST Нет
#Заметка: инструменты можно адаптировать и под аддонские деревья, но только вручную, модифицируя исходный код.

dict_typeToSkfBlid = {
    'SHADER':    'NodeSocketShader',
    'RGB':       'NodeSocketColor', #Для VLNST. todo3 исследовать подробнее.
    'RGBA':      'NodeSocketColor',
    'VECTOR':    'NodeSocketVector',
    'VALUE':     'NodeSocketFloat',
    'STRING':    'NodeSocketString',
    'INT':       'NodeSocketInt',
    'BOOLEAN':   'NodeSocketBool',
    'ROTATION':  'NodeSocketRotation',
    'GEOMETRY':  'NodeSocketGeometry',
    'OBJECT':    'NodeSocketObject',
    'COLLECTION':'NodeSocketCollection',
    'MATERIAL':  'NodeSocketMaterial',
    'TEXTURE':   'NodeSocketTexture',
    'IMAGE':     'NodeSocketImage',
    'CUSTOM':    'NodeSocketVirtual'}
def CollapseBlid(type):
    return dict_typeToSkfBlid.get(type, type)
def CollapseSkBlid(sk):
    return dict_typeToSkfBlid.get(sk.type, sk.type) 

def PrepareShaders(self):
    self.gpuLine = gpu.shader.from_builtin('POLYLINE_SMOOTH_COLOR')
    self.gpuArea = gpu.shader.from_builtin('UNIFORM_COLOR')
    #Параметры, которые не нужно устанавливать каждый раз:
    self.gpuLine.uniform_float('viewportSize', gpu.state.viewport_get()[2:4])
    #todo1 выяснить как или сделать сглаживание для полигонов тоже.
    #self.gpuLine.uniform_float('lineSmooth', True) #Нет нужды, по умолчанию True.
def DrawWay(self, vpos, vcol, wid):
    gpu.state.blend_set('ALPHA') #Рисование текста сбрасывает метку об альфе, поэтому устанавливается каждый раз.
    self.gpuLine.bind()
    self.gpuLine.uniform_float('lineWidth', wid)
    gpu_extras.batch.batch_for_shader(self.gpuLine, 'LINE_STRIP', {'pos':vpos, 'color':vcol}).draw(self.gpuLine)
def DrawAreaFan(self, vpos, col):
    gpu.state.blend_set('ALPHA')
    self.gpuArea.bind()
    self.gpuArea.uniform_float('color', col)
    gpu_extras.batch.batch_for_shader(self.gpuArea, 'TRI_FAN', {'pos':vpos}).draw(self.gpuArea)

#"Низкоуровневое" рисование:
def DrawLine(self, pos1, pos2, siz=1, col1=(1.0, 1.0, 1.0, 0.75), col2=(1.0, 1.0, 1.0, 0.75)):
    DrawWay(self, (pos1,pos2), (col1,col2), siz)
def DrawStick(self, pos1, pos2, col1, col2):
    DrawLine(self, VecWorldToRegScale(pos1, self), VecWorldToRegScale(pos2, self), self.prefs.dsLineWidth, col1, col2)
def DrawRing(self, pos, rd, siz=1, col=(1.0, 1.0, 1.0, 0.75), rotation=0.0, resolution=16):
    vpos = [];  vcol = []
    for cyc in range(resolution+1):
        vpos.append( (rd*math.cos(cyc*2*math.pi/resolution+rotation)+pos[0], rd*math.sin(cyc*2*math.pi/resolution+rotation)+pos[1]) )
        vcol.append(col)
    DrawWay(self, vpos, vcol, siz)
def DrawCircle(self, pos, rd, col=(1.0, 1.0, 1.0, 0.75), resolution=54):
    #Первая вершина гордо в центре круга, остальные по кругу. Нужно было чтобы артефакты сглаживания были красивыми в центр, а не наклонёнными в куда-то бок.
    vpos = ( (pos[0],pos[1]), *( (rd*math.cos(cyc*2.0*math.pi/resolution)+pos[0], rd*math.sin(cyc*2.0*math.pi/resolution)+pos[1]) for cyc in range(resolution+1) ) )
    DrawAreaFan(self, vpos, col)
def DrawRectangle(self, pos1, pos2, col):
    DrawAreaFan(self, ( (pos1[0],pos1[1]), (pos2[0],pos1[1]), (pos2[0],pos2[1]), (pos1[0],pos2[1]) ), col)

#"Высокоуровневое" рисование:
def DrawSocketArea(self, sk, list_boxHeiBou, colfac=Vector(1.0, 1.0, 1.0, 1.0)):
    loc = RecrGetNodeFinalLoc(sk.node)
    pos1 = VecWorldToRegScale( Vector(loc.x, list_boxHeiBou[0]), self )
    pos2 = VecWorldToRegScale( Vector(loc.x+sk.node.width, list_boxHeiBou[1]), self )
    colfac = colfac if self.prefs.dsIsColoredSkArea else GetUniformColVec(self)
    DrawRectangle(self, pos1, pos2, Vector(1.0, 1.0, 1.0, self.prefs.dsSocketAreaAlpha)*colfac)
def DrawIsLinkedMarker(self, loc, ofs, skCol):
    ofs[0] += ( (20*self.prefs.dsIsDrawText+self.prefs.dsDistFromCursor)*1.5+self.prefs.dsFrameOffset )*math.copysign(1,ofs[0])+4
    vec = VecWorldToRegScale(loc, self)
    skCol = skCol if self.prefs.dsIsColoredMarker else GetUniformColVec(self)
    grayCol = 0.65
    col1 = (0.0, 0.0, 0.0, 0.5) #Тень
    col2 = (grayCol, grayCol, grayCol, max(max(skCol[0],skCol[1]),skCol[2])*0.9/2) #Прозрачная белая обводка
    col3 = (skCol[0], skCol[1], skCol[2], 0.925) #Цветная основа
    def DrawMarkerBacklight(tgl, res=16):
        rot = math.pi/res if tgl else 0.0
        DrawRing( self, (vec[0]+ofs[0],     vec[1]+5.0+ofs[1]), 9.0, 3, col2, rot, res )
        DrawRing( self, (vec[0]+ofs[0]-5.0, vec[1]-3.5+ofs[1]), 9.0, 3, col2, rot, res )
    DrawRing( self, (vec[0]+ofs[0]+1.5, vec[1]+3.5+ofs[1]), 9.0, 3, col1)
    DrawRing( self, (vec[0]+ofs[0]-3.5, vec[1]-5.0+ofs[1]), 9.0, 3, col1)
    DrawMarkerBacklight(True) #Маркер рисуется с артефактами "дырявых пикселей". Закостылить их дублированной отрисовкой с вращением.
    DrawMarkerBacklight(False) #Но из-за этого нужно уменьшить альфу белой обводки в два раза.
    DrawRing( self, (vec[0]+ofs[0],     vec[1]+5.0+ofs[1]), 9.0, 1, col3)
    DrawRing( self, (vec[0]+ofs[0]-5.0, vec[1]-3.5+ofs[1]), 9.0, 1, col3)
def DrawWidePoint(self, loc, colfac=Vector(1.0, 1.0, 1.0, 1.0), resolution=54, forciblyCol=False): #"forciblyCol" нужен только для DrawDebug'а.
    #Подготовка:
    pos = VecWorldToRegScale(loc, self)
    loc = Vector(loc.x+6*self.prefs.dsPointRadius*1000, loc.y) #Радиус точки вычисляется через мировое пространство. Единственный из двух, кто зависит от зума в редакторе. Второй -- коробка-подсветка сокетов.
    #Умножается и делится на 1000, чтобы радиус не прилипал к целым числам и тем самым был красивее. Конвертация в экранное пространство даёт только целочисленный результат.
    rd = (VecWorldToRegScale(loc, self)[0]-pos[0])/1000
    #Рисование:
    col1 = Vector(0.5, 0.5, 0.5, 0.4)
    col2 = col1
    col3 = Vector(1.0, 1.0, 1.0, 1.0)
    colfac = colfac if (self.prefs.dsIsColoredPoint)or(forciblyCol) else GetUniformColVec(self)
    rd = (rd*rd+10)**0.5
    DrawCircle(self, pos, rd+3.0, col1*colfac, resolution)
    DrawCircle(self, pos, rd,     col2*colfac, resolution)
    DrawCircle(self, pos, rd/1.5, col3*colfac, resolution)
def DrawText(self, pos, ofs, txt, drawCol, fontSizeOverwrite=0):
    if self.prefs.dsIsAllowTextShadow:
        blf.enable(self.fontId, blf.SHADOW)
        muv = self.prefs.dsShadowCol
        blf.shadow(self.fontId, (0, 3, 5)[self.prefs.dsShadowBlur], muv[0], muv[1], muv[2], muv[3])
        muv = self.prefs.dsShadowOffset
        blf.shadow_offset(self.fontId, muv[0], muv[1])
    else: #Большую часть времени бесполезно, но нужно использовать, когда опция рисования тени переключается.
        blf.disable(self.fontId, blf.SHADOW)
    frameOffset = self.prefs.dsFrameOffset
    blf.size(self.fontId, self.prefs.dsFontSize*(not fontSizeOverwrite)+fontSizeOverwrite)
    #От "текста по факту" не вычисляется, потому что тогда каждая рамка каждый раз будет разной высоты в зависимости от текста.
    #Спецсимвол нужен, как общий случай, чтобы покрыть максимальную высоту. Остальные символы нужны для особых шрифтов, что могут быть выше чем █.
    #Но этого недостаточно, некоторые буквы некоторых шрифтов могут вылезти за рамку. Это не чинится, ибо изначально всё было вылизано и отшлифовано для Consolas.
    #И если починить это для всех шрифтов, то тогда рамка для Consolas'а потеряет красоту.
    #P.s. Consolas -- мой самый любимый шрифт после Comic Sans.
    #Если вы хотите тру-центрирование -- сделайте это сами.
    txtDim = (blf.dimensions(self.fontId, txt)[0], blf.dimensions(self.fontId, "█GJKLPgjklp!?")[1])
    pos = VecWorldToRegScale(pos, self)
    pos = ( pos[0]-(txtDim[0]+frameOffset+10)*(ofs[0]<0)+(frameOffset+1)*(ofs[0]>-1), pos[1]+frameOffset )
    pw = 1/1.975 #Осветлить текст. Почему 1.975 -- не помню.
    placePosY = round( (txtDim[1]+frameOffset*2)*ofs[1] ) #Без округления красивость горизонтальных линий пропадет.
    pos1 = (pos[0]+ofs[0]-frameOffset,              pos[1]+placePosY-frameOffset)
    pos2 = (pos[0]+ofs[0]+10+txtDim[0]+frameOffset, pos[1]+placePosY+txtDim[1]+frameOffset)
    gradientResolution = 12
    girderHeight = 1/gradientResolution*(txtDim[1]+frameOffset*2)
    #Рамка для текста
    if self.prefs.dsDisplayStyle=='CLASSIC': #Красивая рамка
        #Прозрачный фон:
        def Fx(x, a, b):
            return ((x+b)/(b+1))**0.6*(1-a)+a
        for cyc in range(gradientResolution):
            DrawRectangle(self, (pos1[0], pos1[1]+cyc*girderHeight), (pos2[0], pos1[1]+cyc*girderHeight+girderHeight), (drawCol[0]/2, drawCol[1]/2, drawCol[2]/2, Fx(cyc/gradientResolution,0.2,0.05)) )
        #Яркая основная обводка:
        col = (drawCol[0]**pw, drawCol[1]**pw, drawCol[2]**pw, 1.0)
        DrawLine( self,       pos1,        (pos2[0],pos1[1]), 1, col, col)
        DrawLine( self, (pos2[0],pos1[1]),        pos2,       1, col, col)
        DrawLine( self,       pos2,        (pos1[0],pos2[1]), 1, col, col)
        DrawLine( self, (pos1[0],pos2[1]),        pos1,       1, col, col)
        #Мягкая дополнительная обводка, придающая красоты:
        col = (col[0], col[1], col[2], 0.375)
        lineOffset = 2.0
        DrawLine( self, (pos1[0], pos1[1]-lineOffset), (pos2[0], pos1[1]-lineOffset), 1, col, col )
        DrawLine( self, (pos2[0]+lineOffset, pos1[1]), (pos2[0]+lineOffset, pos2[1]), 1, col, col )
        DrawLine( self, (pos2[0], pos2[1]+lineOffset), (pos1[0], pos2[1]+lineOffset), 1, col, col )
        DrawLine( self, (pos1[0]-lineOffset, pos2[1]), (pos1[0]-lineOffset, pos1[1]), 1, col, col )
        #Уголки. Их маленький размер -- маскировка под тру-скругление:
        DrawLine( self, (pos1[0]-lineOffset, pos1[1]), (pos1[0], pos1[1]-lineOffset), 1, col, col )
        DrawLine( self, (pos2[0]+lineOffset, pos1[1]), (pos2[0], pos1[1]-lineOffset), 1, col, col )
        DrawLine( self, (pos2[0]+lineOffset, pos2[1]), (pos2[0], pos2[1]+lineOffset), 1, col, col )
        DrawLine( self, (pos1[0]-lineOffset, pos2[1]), (pos1[0], pos2[1]+lineOffset), 1, col, col )
    elif self.prefs.dsDisplayStyle=='SIMPLIFIED': #Упрощённая рамка. Создана ради нытиков с гипертрофированным чувством дизайнерской эстетики; я вас не понимаю.
        DrawRectangle( self, (pos1[0], pos1[1]), (pos2[0], pos2[1]), (drawCol[0]/2.4, drawCol[1]/2.4, drawCol[2]/2.4, 0.8) )
        col = (0.1, 0.1, 0.1, 0.95)
        DrawLine( self,       pos1,        (pos2[0],pos1[1]), 2, col, col)
        DrawLine( self, (pos2[0],pos1[1]),        pos2,       2, col, col)
        DrawLine( self,       pos2,        (pos1[0],pos2[1]), 2, col, col)
        DrawLine( self, (pos1[0],pos2[1]),        pos1,       2, col, col)
    #Сам текст:
    blf.position(self.fontId, pos[0]+ofs[0]+3.5, pos[1]+placePosY+txtDim[1]*0.3, 0)
    blf.color(   self.fontId, drawCol[0]**pw, drawCol[1]**pw, drawCol[2]**pw, 1.0)
    blf.draw(    self.fontId, txt)
    return (txtDim[0]+frameOffset, txtDim[1]+frameOffset*2)
def DrawSkText(self, pos, ofs, fgSk, fontSizeOverwrite=0):
    if not self.prefs.dsIsDrawText:
        return [1, 0] #"1" нужен для сохранения информации для направления для позиции маркеров
    skCol = GetSkCol(fgSk.tg) if self.prefs.dsIsColoredText else GetUniformColVec(self)
    txt = fgSk.name if fgSk.tg.bl_idname!='NodeSocketVirtual' else TranslateIface('Virtual')
    return DrawText(self, pos, ofs, txt, skCol, fontSizeOverwrite)

#Шаблоны:

def StencilStartDrawCallback(self, context):
    if self.whereActivated!=context.space_data: #Нужно чтобы рисовалось только в активном редакторе, а не во всех у кого открыто то же самое дерево.
        return True
    PrepareShaders(self)
    if self.prefs.dsIsDrawDebug:
        DrawDebug(self, context)

def DrawDoubleNone(self, context):
    cusorPos = context.space_data.cursor_location
    col = Vector(1, 1, 1, 1) if self.prefs.dsIsColoredPoint else GetUniformColVec(self)
    vec = Vector(self.prefs.dsPointOffsetX*0.75, 0)
    if (self.prefs.dsIsDrawLine)and(self.prefs.dsIsAlwaysLine):
        DrawStick( self, cusorPos-vec, cusorPos+vec, col, col )
    if self.prefs.dsIsDrawPoint:
        DrawWidePoint(self, cusorPos-vec, col)
        DrawWidePoint(self, cusorPos+vec, col)
def CallbackDrawEditTreeIsNone(self, context): #Именно. Ибо эстетика. Вдруг пользователь потеряется; нужно подать признаки жизни.
    if StencilStartDrawCallback(self, context):
        return
    if self.prefs.dsIsDrawPoint:
        cusorPos = context.space_data.cursor_location
        if getattr(self,'isDrawDoubleNone', False):
            DrawDoubleNone(self, context)
        else:
            DrawWidePoint(self, cusorPos)

def DrawDebug(self, context):
    def DebugTextDraw(pos, txt, r, g, b):
        blf.size(0,18);  blf.position(0, pos[0]+10,pos[1], 0);  blf.color(0, r,g,b,1.0);  blf.draw(0, txt)
    cusorPos = context.space_data.cursor_location
    DebugTextDraw(VecWorldToRegScale(cusorPos, self), "Cursor position here.", 1, 1, 1)
    if not context.space_data.edit_tree:
        return
    list_nodes = GetNearestNodes(context.space_data.edit_tree.nodes, cusorPos)
    col = Vector(1, 0.5, 0.5, 1)
    DrawStick( self, cusorPos, list_nodes[0].pos, col, col )
    sco = 0
    for li in list_nodes:
        DrawWidePoint(self, li.pos, col, 4, True)
        DebugTextDraw( VecWorldToRegScale(li.pos, self), str(sco)+" Node goal here", col.x, col.y, col.z )
        sco += 1
    list_fgSksIn, list_fgSksOut = GetNearestSockets(list_nodes[0].tg, cusorPos)
    if list_fgSksIn:
        DrawWidePoint( self, list_fgSksIn[0].pos, Vector(0.5, 1, 0.5, 1), 4, True )
        DebugTextDraw( VecWorldToRegScale(list_fgSksIn[0].pos, self), "Nearest socketIn here", 0.5, 1, 0.5)
    if list_fgSksOut:
        DrawWidePoint( self, list_fgSksOut[0].pos, Vector(0.5, 0.5, 1, 1), 4, True )
        DebugTextDraw( VecWorldToRegScale(list_fgSksOut[0].pos, self), "Nearest socketOut here", 0.75, 0.75, 1)

def DrawNodeStencil(self, cusorPos, pos):
    colNode = PowerArr4ToVec(self.prefs.dsNodeColor, 1/2.2)
    col = colNode if self.prefs.dsIsColoredLine else GetUniformColVec(self)
    if self.prefs.dsIsDrawLine:
        DrawStick( self, pos, cusorPos, col, col )
    if self.prefs.dsIsDrawPoint:
        DrawWidePoint( self, pos, colNode if self.prefs.dsIsColoredPoint else GetUniformColVec(self) )
    return colNode
def DrawTextNodeStencil(self, cusorPos, nd, drawNodeNameLabel, labelDispalySide, col=Vector(1, 1, 1, 1)):
    if not self.prefs.dsIsDrawText:
        return
    def DrawNodeText(txt):
        if txt:
            DrawText( self, cusorPos, (self.prefs.dsDistFromCursor, -0.5), txt, col)
    col = col if self.prefs.dsIsColoredText else GetUniformColVec(self)
    txt_label = nd.label
    match drawNodeNameLabel:
        case 'NAME':
            DrawNodeText(nd.name)
        case 'LABEL':
            DrawNodeText(txt_label if txt_label else None)
        case 'LABELNAME':
            if not txt_label:
                DrawNodeText(nd.name)
                return
            match labelDispalySide:
                case 1: tuple_side = (1, 1, 0.25)
                case 2: tuple_side = (1, 1, -1.25)
                case 3: tuple_side = (1, -1, -0.5)
                case 4: tuple_side = (-1, 1, -0.5)
            DrawText( self, cusorPos, (self.prefs.dsDistFromCursor*tuple_side[0], tuple_side[2]), nd.name, col)
            DrawText( self, cusorPos, (self.prefs.dsDistFromCursor*tuple_side[1], -tuple_side[2]-1), txt_label, col)
def DrawNodeStencilFull(self, cusorPos, fg, txtDnnl, lds, isCanText=True):
    if fg:
        #Нод не имеет цвета (в этом аддоне вся тусовка ради сокетов, так что нод не имеет цвета, ок да?.)
        #Поэтому, для нода всё одноцветное -- пользовательское для нода, или пользовательское постоянной перезаписи.
        colNode = DrawNodeStencil(self, cusorPos, fg.pos)
        if isCanText:
            DrawTextNodeStencil(self, cusorPos, fg.tg, txtDnnl, lds, colNode)
        else:
            return colNode #Для VEST.
    elif self.prefs.dsIsDrawPoint:
        DrawWidePoint(self, cusorPos)
    return False

#Высокоуровневый шаблон рисования для сокетов; тут весь аддон про сокеты, поэтому в названии нет "Sk".
#Пользоваться этим шаблоном невероятно кайфово, после того хардкора что был в ранних версиях (даже не заглядывайте туда, там около-ад).
def DrawToolOftenStencil(self, cusorPos, list_twoTgSks, #Одинаковое со всех инструментов вынесено в этот шаблон.
                         isLineToCursor=False,
                         textSideFlip=False,
                         isDrawText=True,
                         isDrawMarkersMoreTharOne=False,
                         isDrawOnlyArea=False):
    def GetVecOffsetFromSk(sk, y=0.0):
        return Vector(self.prefs.dsPointOffsetX*((sk.is_output)*2-1), y)
    try:
        #Вся суета ради линии:
        if (self.prefs.dsIsDrawLine)and(not isDrawOnlyArea):
            len = length(list_twoTgSks)
            if self.prefs.dsIsColoredLine:
                col1 = GetSkCol(list_twoTgSks[0].tg)
                col2 = Vector(1, 1, 1, 1) if self.prefs.dsIsColoredPoint else GetUniformColVec(self)
                col2 = col2 if (isLineToCursor)or(len==1) else GetSkCol(list_twoTgSks[1].tg)
            else:
                col1 = GetUniformColVec(self)
                col2 = col1
            if len>1: #Ниже могут нарисоваться две палки одновременно. Эта ситуация вручную обрабатывается в вызывающей функции на стек выше.
                DrawStick( self, list_twoTgSks[0].pos+GetVecOffsetFromSk(list_twoTgSks[0].tg), list_twoTgSks[1].pos+GetVecOffsetFromSk(list_twoTgSks[1].tg), col1, col2 )
            if isLineToCursor:
                DrawStick( self, list_twoTgSks[0].pos+GetVecOffsetFromSk(list_twoTgSks[0].tg), cusorPos, col1, col2 )
        #Всё остальное:
        for li in list_twoTgSks:
            if self.prefs.dsIsDrawSkArea:
                DrawSocketArea( self, li.tg, li.boxHeiBound, GetSkColPowVec(li.tg, 1/2.2) )
            if (self.prefs.dsIsDrawPoint)and(not isDrawOnlyArea):
                DrawWidePoint( self, li.pos+GetVecOffsetFromSk(li.tg), GetSkColPowVec(li.tg, 1/2.2) )
        if isDrawText:
            for li in list_twoTgSks:
                side = (textSideFlip*2-1)
                txtDim = DrawSkText( self, cusorPos, (self.prefs.dsDistFromCursor*(li.tg.is_output*2-1)*side, -0.5), li )
                #В условии ".links", но не ".is_linked", потому что линки могут быть выключены (замьючены, красные)
                if (self.prefs.dsIsDrawMarker)and( (li.tg.links)and(not isDrawMarkersMoreTharOne)or(length(li.tg.links)>1) ):
                    DrawIsLinkedMarker( self, cusorPos, [txtDim[0]*(li.tg.is_output*2-1)*side, 0], GetSkCol(li.tg) )
    except Exception as ex:
        pass; print("VL DrawToolOftenStencil() --", ex)

#todo2 Головная боль с "проскальзывающими" кадрами!! Debug, Collapse, Alt, и много где ещё.

def GetOpKmi(self, tuple_tar): #todo0 есть ли концепция или способ правильнее?
    #return GetUserKmNe().keymap_items[getattr(bpy.types, self.bl_idname).bl_idname] #Если без дубликатов.
    txt_toolBlId = getattr(bpy.types, self.bl_idname).bl_idname
    #Оператор может иметь несколько комбинаций вызова, все из которых будут одинаковы по ключу в `keymap_items`, от чего за константу кажись никак не распознать.
    #Поэтому перебираем всех вручную
    for li in GetUserKmNe().keymap_items:
        if li.idname==txt_toolBlId:
            #Заметка: искать и по соответствию самой клавише тоже, модификаторы тоже могут быть одинаковыми у нескольких вариантах вызова.
            if (li.type==tuple_tar[0])and(li.shift_ui==tuple_tar[1])and(li.ctrl_ui==tuple_tar[2])and(li.alt_ui==tuple_tar[3]):
                #Заметка: могут быть и два идентичных хоткеев вызова, но Blender будет выполнять только один из них (по крайней мере для VL), тот, который будет первее в списке.
                return li # Эта функция так же выдаёт первого в списке.
def ForseSetSelfNonePropToDefault(kmi, self):
    if not kmi:
        return
    #Если в keymap в вызове оператора не указаны его свойства, они читаются от последнего вызова. Эта функция призвана устанавливать их обратно по умолчанию.
    for li in self.rna_type.properties:
        if li.identifier!='rna_type':
            #Заметка: определить установленность в kmi -- наличие `kmi.properties[li.identifier]`.
            setattr(self, li.identifier, getattr(kmi.properties, li.identifier)) #Ради этого мне пришлось реверсинженерить Blender с отладкой. А ларчик просто открывался...

#Теперь ООП иерархия.
class VoronoiOp(bpy.types.Operator):
    bl_options = {'UNDO'} #Вручную созданные линки undo'тся, так что и в VL ожидаемо тоже. И вообще для всех.
    @classmethod
    def poll(cls, context):
        return context.area.type=='NODE_EDITOR' #Не знаю, зачем это нужно, но пусть будет.
class VoronoiTool(VoronoiOp): #Корень для инструментов.
    #Всегда неизбежно происходит кликанье в дереве, где обитают ноды, поэтому для всех инструментов
    isPassThrough: bpy.props.BoolProperty(name="Pass through node selecting", description="Clicking over a node activates selection, not the tool", default=False)
    #Заметка: NextAssignment имеется у всех; и теперь он одинаков по количеству параметров, чтобы проще обрабатываться шаблонами.
class VoronoiToolSk(VoronoiTool):
    pass
class VoronoiToolDblSk(VoronoiToolSk):
    isCanBetweenFields: bpy.props.BoolProperty(name="Can between fields", description="Tools can connecting between different field types", default=True)
class VoronoiToolNd(VoronoiTool):
    pass
class VoronoiToolSkNd(VoronoiToolSk, VoronoiToolNd):
    pass


set_skTypeArrFields = {'VECTOR', 'RGBA', 'ROTATION'}
def SkBetweenFieldsCheck(self, sk1, sk2):
    #Заметка: учитывая предназначение и название этой функции, sk1 и sk2 в любом случае должны быть из полей, и только из них.
    return (sk1.type in set_skTypeFields)and( (self.isCanBetweenFields)and(sk2.type in set_skTypeFields)or(sk1.type==sk2.type) )

def MinFromFgs(fgSk1, fgSk2): #VST, VHT, и VDT.
    if (fgSk1)or(fgSk2): #Если хотя бы один из них существует.
        if not fgSk2: #Если одного из них не существует,
            return fgSk1
        elif not fgSk1: # то остаётся однозначный выбор для второго.
            return fgSk2
        else: #Иначе выбрать ближайшего.
            return fgSk1 if fgSk1.dist<fgSk2.dist else fgSk2
    return None


def ProcCanMoveOut(self, event):
    #Инверсия с '^[5]', чтобы в случае хоткея на одну кнопку без модификаторов, можно было делать перевыбор любым из модификаторов.
    if self.dict_isMoveOutSco[0]==0:
        if not(event.shift or event.ctrl or event.alt)^self.dict_isMoveOutSco[5]: #|3| Но не от первого отжатия. Оно должно быть полностью никакими. Ибо эстетика, и я так захотел.
            self.dict_isMoveOutSco[0] = 1
    else:
        if self.prefs.vtRepickTrigger=='FULL': #Переключать каждый раз при входе и выходе из карты
            tgl = ( (event.shift==self.dict_isMoveOutSco[1])and(event.ctrl==self.dict_isMoveOutSco[2])and(event.alt==self.dict_isMoveOutSco[3]) )^self.dict_isMoveOutSco[5]
        else: #Переключать каждый раз при нажатии и отжатии любого из модификаторов
            tgl = (event.shift)or(event.ctrl)or(event.alt)
        if tgl!=self.dict_isMoveOutSco[4]:
            self.dict_isMoveOutSco[4] = tgl
            self.dict_isMoveOutSco[0] += 1
    return not(self.dict_isMoveOutSco[0]%2)and(self.dict_isMoveOutSco[0]>1)

def StencilReNext(self, context, *naArgs):
    #Алерт! 'DRAW_WIN' вызывает краш для некоторых редких деревьев со свёрнутыми нодами! #todo3 забагрепортить бы это.
    bpy.ops.wm.redraw_timer(type='DRAW', iterations=0) #Заставляет курсор меняться на мгновенье (по крайней мере на винде).
    #Заметка: осторожно с вызозом StencilReNext() в NextAssignment(), чтобы не уйти в вечный цикл!
    self.NextAssignment(context, *naArgs) #Заметка: не забывать разворачивать нарезку.

#Мейнстримные шаблоны, отсортированные в порядке по нахождению в коде:

def StencilMouseNextAndReout(self, context, event, *naArgsDouble): #Заметка: аккуратнее с naDoubleArgs, должен быть всегда чётным.
    #Заметка: первым в naArgsDouble -- для False (as отсутствие isBoth), ибо оно первичнее.
    context.area.tag_redraw()
    half = length(naArgsDouble)//2
    #ProcCanMoveOut за пределами match event.type, потому что должно обрабатываться не только от движения курсора, а сразу после нажатия модификатора.
    isCanReOut = ProcCanMoveOut(self, event) if naArgsDouble else False
    if isCanReOut:
        self.NextAssignment(context, *naArgsDouble[half:]) #И тут тоже не забывать разворачивать.
    match event.type:
        case 'MOUSEMOVE':
            if not isCanReOut: #Но не делать двойную обработку, если оно уже выше; или всегда проходит, если нет ProcCanMoveOut()'а.
                self.NextAssignment(context, *naArgsDouble[:half])
        case self.kmi.type|'ESC': #Раньше было `self.keyType` и `.. = kmi.type`, теперь имеется полный kmi.
            return True
    return False

#todo1 обработать все комбинации в n^3: space_data.tree_type и space_data.edit_tree.bl_idname; классическое, потерянное, и аддонское; привязанное и не привязанное к редактору.
#todo1 И потом работоспособность всех инструментов в них. А потом проверить в существующем дереве взаимодействие потерянного сокета у потерянного нода для инструментов.
def UselessForCustomUndefTrees(context, isForCustom=True, isForUndef=True): #'isForCustom' ради VPAT. Второй для компании.
    tree = context.space_data.edit_tree
    if not tree:
        return {'FINISHED'} #CANCELLED
    txt_treeBlid = tree.bl_idname
    if (isForUndef)and(txt_treeBlid=='NodeTreeUndefined'): #Для поломанного дерева space_data.tree_type==''. А я то думал это просто ссылка.
        return {'CANCELLED'} #В отличие от StencilModalEsc(), здесь покидается для не-рисования.
    elif (isForCustom)and(txt_treeBlid not in {'ShaderNodeTree','GeometryNodeTree','CompositorNodeTree','TextureNodeTree'}):
        return {'PASS_THROUGH'} #CANCELLED
    return {}

def StencilModalEsc(self, context, event):
    if event.type=='ESC': #Собственно то, что и должна делать клавиша побега.
        return {'CANCELLED'}
    if event.value!='RELEASE':
        return {'RUNNING_MODAL'}
    bpy.types.SpaceNodeEditor.draw_handler_remove(self.handle, 'WINDOW')
    if not context.space_data.edit_tree:
        return {'FINISHED'}
    RestoreCollapsedNodes(context.space_data.edit_tree.nodes)
    #В потерянном дереве любому инструменту нечего-то особо делать, поэтому принесено сюда в шаблон.
    tree = context.space_data.edit_tree #Для проверки на существование, чтобы наверняка.
    if (tree)and(tree.bl_idname=='NodeTreeUndefined'): #|1| Если дерево нодов от к.-н. аддона исчезло, то остатки имеют NodeUndefined и NodeSocketUndefined.
        return {'CANCELLED'} #Через api линки на SocketUndefined всё равно не создаются, да и делать в этом дереве особо нечего, поэтому выходим.
    return False

def StencilProcPassThrought(self, context): #Вынесено вовне для VPAT.
    #Одинаковая для всех инструментов обработка пропуска выделения
    tree = context.space_data.edit_tree
    if (self.isPassThrough)and(tree)and('FINISHED' in bpy.ops.node.select('INVOKE_DEFAULT')): #Проверка на дерево вторым, для эстетической оптимизации.
        #Если хоткей вызова инструмента совпадает со снятием выделения, то выделенный строчкой выше нод будет де-выделен обратно после передачи эстафеты (но останется активным).
        #Поэтому для таких ситуаций нужно снимать выделение, чтобы снова произошло переключение обратно на выделенный.
        tree.nodes.active.select = False #Но без условий, для всех подряд. Ибо ^иначе будет всегда выделение без переключения; и у меня нет идей, как бы я парился с распознаванием таких ситуаций.
        return {'PASS_THROUGH'}
    return {}
def StencilBeginToolInvoke(self, context, event):
    self.prefs = Prefs() #А ларчик просто открывался.
    self.kmi = GetOpKmi(self, (event.type, event.shift, event.ctrl, event.alt))
    isPass = StencilProcPassThrought(self, context)
    if not isPass: #Для оптимизации; если всё равно завершится без выполнения с пропуском, то телодвижения ниже бесполезны.
        ForseSetSelfNonePropToDefault(self.kmi, self) #Имеет смысл как можно раньше. Актуально для VQMT и VEST (и из-за них переехало из StencilToolWorkPrepare сюда).
        #"0" -- количество хитов, 1..3 -- карта проверки, 4 -- предыдущее состояние переключателя, 5 -- метка активации без модификаторов; `4:False` потому что см. |3|.
        self.dict_isMoveOutSco = {0:0, 1:self.kmi.shift_ui, 2:self.kmi.ctrl_ui, 3:self.kmi.alt_ui, 4:False, 5:not(self.kmi.shift_ui or self.kmi.ctrl_ui or self.kmi.alt_ui)}
        #Заметка: self.dict_isMoveOutSco будет читаться только через StencilMouseNextAndReout(), а он будет вызываться при работе инструмента. Так что находится в ветвлении isPass.
    return isPass

def StencilToolWorkPrepare(self, context, Func, *naArgs):
    #Здесь был dict_isMoveOutSco; переехал в StencilBeginToolInvoke зацепом с self.kmi и ForseSetSelfNonePropToDefault().
    #Древний мейнстрим (этот кусок кода не изменялся со времен динозавров): #todo1 найти бы версию vl, когда такое появилось.
    self.uiScale = UiScale()
    self.whereActivated = context.space_data #CallBack'и рисуются во всех редакторах. Но в тех, у кого нет целевого сокета -- выдаёт ошибку и тем самым ничего не рисуется.
    self.fontId = blf.load(self.prefs.dsFontFile) #Постоянная установка шрифта нужна чтобы шрифт не исчезал при смене темы оформления.
    context.area.tag_redraw() #Не нужно в основном, но тогда в кастомных деревьях с нодами без сокетов точка при активации (VMT) не появляется сразу.
    #Финальная подготовка к работе:
    tree = context.space_data.edit_tree
    if tree:
        SaveCollapsedNodes(tree.nodes)
    Func = Func if tree else CallbackDrawEditTreeIsNone
    self.handle = bpy.types.SpaceNodeEditor.draw_handler_add(Func, (self,context), 'WINDOW', 'POST_PIXEL')
    context.window_manager.modal_handler_add(self)
    self.NextAssignment(context, naArgs)
    #return not not tree #Теперь в этом нет нужды.

skf4sucess = -1

#P.s. не знаю, что значит "ViaVer", просто прикольный набор букф.

def ViaVerNewSkf(tree, side, skType, name):
    isSk = type(skType)!=str
    if isBlender4:
        global skf4sucess
        if skf4sucess==-1:
            skf4sucess = 1+hasattr(tree.interface,'items_tree')
        match skf4sucess:
            case 1: skf = tree.interface.new_socket(name, in_out={'OUTPUT' if side else 'INPUT'}, socket_type=CollapseSkBlid(skType) if isSk else skType)
            case 2: skf = tree.interface.new_socket(name, in_out='OUTPUT' if side else 'INPUT', socket_type=CollapseSkBlid(skType) if isSk else skType)
    else:
        skf = (tree.outputs if side else tree.inputs).new(skType.bl_idname if isSk else skType, name)
    return skf
def ViaVerGetSkfi(tree, side):
    if isBlender4:
        global skf4sucess
        if skf4sucess==-1:
            skf4sucess = 1+hasattr(tree.interface,'items_tree')
        match skf4sucess:
            case 1: return tree.interface.ui_items
            case 2: return tree.interface.items_tree
    else:
        return (tree.outputs if side else tree.inputs)
def ViaVerGetSkf(tree, side, name):
    return ViaVerGetSkfi(tree, side).get(name)
def NewSkfFromSk(tree, side, sk):
    def FixDefaultSkf(tree, idf, val):
        def FixTree(tr):
            for nd in tr.nodes:
                if (nd.type=='GROUP')and(nd.node_tree==tree):
                    for sk in nd.inputs:
                        if sk.identifier==idf:
                            sk.default_value = val
        for ng in bpy.data.node_groups:
            FixTree(ng)
        for mt in bpy.data.materials:
            if mt.node_tree: #На основе багрепорта; я так и не понял, каким образом оно может быть None.
                FixTree(mt.node_tree)
        #Остальные (например свет или композитинг) обделены. Ибо костыль.
    skf = ViaVerNewSkf(tree, side, sk, GetSkLabelName(sk))
    skf.hide_value = sk.hide_value
    if hasattr(skf,'default_value'):
        skf.default_value = sk.default_value
        #todo1 нужно придумать как внедриться до создания, чтобы у всех групп появился сокет со значением сразу же от sfk default.
        FixDefaultSkf(tree, skf.identifier, sk.default_value)
        if hasattr(skf,'min_value'):
            nd = sk.node
            if (nd.type=='GROUP')and(nd.node_tree): #Если сокет от другой группы нодов, то полная копия.
                ng = nd.node_tree
                skfiNg = ViaVerGetSkfi(ng, sk.is_output)
                for skfNg in skfiNg:
                    if skfNg.identifier==sk.identifier:
                        #skf.min_value = skfNg.min_value
                        #skf.max_value = skfNg.max_value
                        for pr in skf.rna_type.properties:
                            if not(pr.is_readonly or pr.is_registered):
                                setattr(skf, pr.identifier, getattr(skfNg, pr.identifier))
                        break
    return skf
def ViaVerSkfRemove(tree, side, name):
    if isBlender4:
        tree.interface.remove(name)
    else:
        (tree.outputs if side else tree.inputs).remove(name)

import ctypes

#Аааа, я просто сделалъ на досуге VLT на 157 строчки; чёрт возьми, что тут происходит??

#../source/blender/makesdna/DNA_node_types.h
class StructBase(ctypes.Structure):
    _subclasses = []
    __annotations__ = {}
    def __init_subclass__(cls):
        cls._subclasses.append(cls)
    @staticmethod
    def _init_structs():
        """Initialize subclasses, converting annotations to fields."""
        functype = type(lambda:None)
        for cls in StructBase._subclasses:
            fields = []
            for field, value in cls.__annotations__.items():
                if isinstance(value, functype):
                    value = value()
                fields.append((field, value))
            if fields:
                cls._fields_ = fields
            cls.__annotations__.clear()
        StructBase._subclasses.clear()
class BVector(StructBase):
    begin:        ctypes.c_void_p
    end:          ctypes.c_void_p
    capacity_end: ctypes.c_void_p
    _pad:         ctypes.c_char*32
class BNodeSocketRuntimeHandle(StructBase):
    if not isLinux:
        _pad0:                            ctypes.c_char*8
    declaration:                      ctypes.c_void_p
    changed_flag:                     ctypes.c_uint32
    total_inputs:                     ctypes.c_short
    _pad1:                            ctypes.c_char*2
    location:                         ctypes.c_float*2
    directly_linked_links:            BVector
    directly_linked_sockets:          BVector
    logically_linked_sockets:         BVector
    logically_linked_skipped_sockets: BVector
    owner_node:                       ctypes.c_void_p
    internal_link_input:              ctypes.c_void_p
    index_in_node:                    ctypes.c_int
    index_in_all_sockets:             ctypes.c_int
    index_in_inout_sockets:           ctypes.c_int
class BNodeStack(StructBase):
    vec:        ctypes.c_float*4
    min:        ctypes.c_float
    max:        ctypes.c_float
    data:       ctypes.c_void_p
    hasinput:   ctypes.c_short
    hasoutput:  ctypes.c_short
    datatype:   ctypes.c_short
    sockettype: ctypes.c_short
    is_copy:    ctypes.c_short
    external:   ctypes.c_short
    _pad:       ctypes.c_char*4
class BNodeSocket(StructBase):
    next:           lambda: ctypes.POINTER(BNodeSocket)
    prev:           lambda: ctypes.POINTER(BNodeSocket)
    prop:                   ctypes.c_void_p
    identifier:             ctypes.c_char*64
    name:                   ctypes.c_char*64
    storage:                ctypes.c_void_p
    in_out:                 ctypes.c_short
    typeinfo:               ctypes.c_void_p
    idname:                 ctypes.c_char*64
    default_value:          ctypes.c_void_p
    _pad:                   ctypes.c_char*4
    label:                  ctypes.c_char*64
    description:            ctypes.c_char*64    
    if (isBlender4)and(bpy.app.version_string!='4.0.0 Alpha'):
        short_label:            ctypes.c_char*64
    default_attribute_name: ctypes.POINTER(ctypes.c_char)
    to_index:               ctypes.c_int
    link:                   ctypes.c_void_p
    ns:                     BNodeStack
    runtime:                ctypes.POINTER(BNodeSocketRuntimeHandle)
    @classmethod
    def GetLocation(cls, so):
        return cls.from_address(so.as_pointer()).runtime.contents.location[:]
StructBase._init_structs()
#Спасибо пользователю с ником "Oxicid", за этот кусок кода с ctypes. "А что, так можно было?".
#Ох уж эти разрабы; пришлось самому добавлять возможность получать позиции сокетов. Месево от Blender 4.0 прижало к стенке и вынудило.
#Это получилось сделать аш на питоне, неужели так сложно было пронести api?

def GetSkLocVec(sk):
    if (sk.enabled)and(not sk.hide):
        return mathutils.Vector(BNodeSocket.GetLocation(sk))
    else:
        return Vector(0, 0)
#Что ж, самое сложное пройдено. До технической возможности поддерживать свёрнутые ноды осталось всего ничего.
#Жаждущие это припрутся сюда по-быстрому на покерфейсе, возьмут что нужно, и модифицируют себе.
#Тот первый, кто это сделает, моё тебе послание: "Что ж, молодец. Теперь ты можешь сосаться к сокетам свёрнутого нода. Надеюсь у тебя счастья полные штаны".

#Обеспечивает поддержку свёрнутых нодов:
#Дождались таки. Конечно же не "честную поддержку". Я презираю свёрнутые ноды, и у меня нет желания шататься с округлостью, и соответствующе изменённым рисованием.
#Так что до введения api на позицию сокета, это лучшее что есть. Ждём и надеемся.
dict_collapsedNodes = {}
def SaveCollapsedNodes(nodes):
    dict_collapsedNodes.clear()
    for nd in nodes:
        dict_collapsedNodes[nd] = nd.hide
#Я не стал показывать развёрнутым только ближайший нод, а сделал этакий "след".
#Чтобы всё это не превращалось в хаос с постоянным "дёрганьем", и чтобы можно было провести, раскрыть, успокоиться, увидеть "местную картину", и спокойно соединить что нужно.
def RestoreCollapsedNodes(nodes):
    for nd in nodes:
        if dict_collapsedNodes.get(nd, False): #Инструменты могут создавать ноды в процессе; например, сохранение результата в Preview'е.
            nd.hide = dict_collapsedNodes[nd]

def StencilUnCollapseNode(nd, tar=True):
    #if type(tar)==str: tar = isInverse #Остаток от возможности разворачивания нода "в любом случае".
    #if (self.prefs.vtAlwaysUnhideCursorNode)or(tar)and( not(isInverse and self.prefs.vtAlwaysUnhideCursorNode) ): #Запаянная старая версия.
    if tar: #Стало проще, но избавляться от этой функции не стоит, потому что количество вызовов особо не изменилось, ибо 'isBoth'.
        result = nd.hide
        nd.hide = False
        return result
    return False

class FoundTarget:
    def __init__(self, tg=None, dist=0.0, pos=Vector(0.0, 0.0), boxHeiBound=(0.0, 0.0), txt=''):
        self.tg = tg
        self.dist = dist
        self.pos = pos
        #Далее нужно только для сокетов.
        self.boxHeiBound = boxHeiBound
        self.name = txt #Нужен для поддержки перевода на другие языки. Получать перевод каждый раз при рисовании слишком не комильфо, поэтому вычисляется в заранее.

def DistanceField(field0, boxbou): #Спасибо RayMarching'у, без него я бы до такого не допёр.
    #Все vec2:
    field1 = Vector((field0.x>0)*2-1, (field0.y>0)*2-1)
    field0 = Vector(abs(field0.x), abs(field0.y))-boxbou/2
    field2 = Vector(max(field0.x, 0), max(field0.y, 0))
    field3 = Vector(abs(field0.x), abs(field0.y))
    field3 = field3*Vector(field3.x<=field3.y, field3.x>field3.y)
    field3 = field3*-( (field2.x+field2.y)==0 )
    return (field2+field3)*field1
def GetNearestNode(nd, pos, uiScale=None): #Вычленено из GetNearestNodes(), без нужды, но VLTT вынудил.
    if not uiScale:
        uiScale = UiScale()
    ndLoс = RecrGetNodeFinalLoc(nd) #Расчехлить иерархию родителей и получить итоговую позицию нода. Проклятые рамки, чтоб их.
    isReroute = nd.bl_idname=='NodeReroute'
    #Технический размер рероута явно перезаписан в 4 раза меньше, чем он есть.
    #Насколько я смог выяснить, рероут в отличие от остальных нодов свои размеры при изменении uiScale не меняет. Так что ему не нужно делиться на 'uiScale'.
    ndSize = Vector(4,4) if isReroute else nd.dimensions/uiScale
    #Для нода позицию в центр нода. Для рероута позиция уже в его визуальном центре
    ndCenter = ndLoс.copy() if isReroute else ndLoс+ndSize/2*Vector(1,-1)
    if nd.hide: #Для VHT, "шустрый костыль" из имеющихся возможностей.
        ndCenter.y += ndSize.y/2-10 #Нужно быть аккуратнее с этой записью(write), ибо оно может оказаться указателем напрямую, если выше нодом является рероут.
    #Сконструировать поле расстояний
    vec = DistanceField(pos-ndCenter, ndSize)
    #Добавить в список отработанный нод
    return FoundTarget(nd, vec.length, pos-vec)
def GetNearestNodes(nodes, callPos, skipPoorNodes=True): #Выдаёт список ближайших нод. Честное поле расстояний.
    #Почти честное. Скруглённые уголки не высчитываются. Их отсутствие не мешает, а вычисление требует больше телодвижений. Поэтому выпендриваться нет нужды.
    #С другой стороны скруглённость актуальна для свёрнутых нод, но я их презираю, так что...
    list_foundNodes = [] #todo0 париться с питоновскими и вообще ускорениями буду ещё не скоро.
    uiScale = UiScale()
    for nd in nodes:
        if nd.type=='FRAME': #Рамки пропускаются, ибо ни одному инструменту они не нужны.
            continue
        if (skipPoorNodes)and(not nd.inputs)and(not nd.outputs): #Ноды вообще без ничего -- как рамки. Почему бы их тоже не игнорировать ещё на этапе поиска?
            continue
        list_foundNodes.append( GetNearestNode(nd, callPos, uiScale) )
    list_foundNodes.sort(key=lambda a: a.dist)
    return list_foundNodes

#Уж было я хотел добавить велосипедную структуру ускорения, но внезапно осознал, что ещё нужна информация об "вторых ближайших". Так что кажись без полной обработки никуда.
#Если вы знаете, как можно это ускорить с сохранением информации, поделитесь со мной.
#С другой стороны, за всё время существования аддона не было ни одной стычки с производительностью, так что... только ради эстетики.
#А ещё нужно учитывать свёрнутые ноды, пропади они пропадом, которые могут раскрыться в процессе, наворачивая всю прелесть кеширования.

def GetFromIoPuts(nd, side, callPos): #Вынесено для Preview Tool его опции 'vpRvEeSksHighlighting'.
    def SkIsLinkedVisible(sk):
        if not sk.is_linked:
            return True
        return (sk.links)and(sk.links[0].is_muted)
    list_result = []
    ndLoc = RecrGetNodeFinalLoc(nd)
    #"nd.dimensions" уже содержат в себе корректировку на масштаб интерфейса, поэтому вернуть его обратно в мир делением
    uiScale = UiScale()
    ndDim = mathutils.Vector(nd.dimensions/uiScale)
    for sk in nd.outputs if side else reversed(nd.inputs):
        #Игнорировать выключенные и спрятанные
        if (sk.enabled)and(not sk.hide):
            posSk = GetSkLocVec(sk)/uiScale #Чорт возьми, это офигенно. Долой велосипедный кринж прошлых версий.
            #todo3 найти то свойство, отвечающая за высоту сокета у нода (и аннигилировать SkIsLinkedVisible). А пока остатками от велосипеда:
            #^ если вектор(массив) от кастомных нодов, то ручная проверка на вектор бесполезна. Нужно придумать как определить массив от обычного сокета.
            muv = 0
            if (not side)and(sk.type=='VECTOR')and(SkIsLinkedVisible(sk))and(not sk.hide_value):
                if str(sk.rna_type).find("VectorDirection")!=-1:
                    muv = 2
                elif ( not( (nd.type in ('BSDF_PRINCIPLED','SUBSURFACE_SCATTERING'))and(not isBlender4) ) )or( not(sk.name in ("Subsurface Radius","Radius"))):
                    muv = 3
            list_result.append(FoundTarget( sk,
                                            (callPos-posSk).length,
                                            posSk,
                                            (posSk.y-11-muv*20, posSk.y+11+max(length(sk.links)-2,0)*5*(not side)),
                                            TranslateIface(GetSkLabelName(sk)) ))
    return list_result
def GetNearestSockets(nd, callPos): #Выдаёт список "ближайших сокетов". Честное поле расстояний ячейками Вороного. Да, да, аддон назван именно из-за этого.
    list_fgSksIn = []
    list_fgSksOut = []
    if not nd: #Если искать не у кого
        return list_fgSksIn, list_fgSksOut
    #Если рероут, то имеем тривиальный вариант, не требующий вычисления; вход и выход всего одни, позиции сокетов -- он сам
    if nd.bl_idname=='NodeReroute':
        ndLoc = RecrGetNodeFinalLoc(nd)
        len = (callPos-ndLoc).length
        L = lambda who: FoundTarget(who[0], len, ndLoc, (-1,-1), TranslateIface(who[0].name))
        return [L(nd.inputs)], [L(nd.outputs)]
    list_fgSksIn = GetFromIoPuts(nd, False, callPos)
    list_fgSksOut = GetFromIoPuts(nd, True, callPos)
    list_fgSksIn.sort(key=lambda a: a.dist)
    list_fgSksOut.sort(key=lambda a: a.dist)
    return list_fgSksIn, list_fgSksOut

#Возможно когда-нибудь придётся добавить "область активации", возвращение курсора в которую намеренно делает результат работы инструмента никаким. Актуально для VST с 'isIgnoreLinked'.

def CallbackDrawVoronoiLinker(self, context):
    if StencilStartDrawCallback(self, context):
        return
    cusorPos = context.space_data.cursor_location
    if not self.foundGoalSkOut:
        DrawDoubleNone(self, context)
    elif (self.foundGoalSkOut)and(not self.foundGoalSkIn):
        DrawToolOftenStencil( self, cusorPos, [self.foundGoalSkOut], isLineToCursor=self.prefs.dsIsAlwaysLine )
        if self.prefs.dsIsDrawPoint: #Точка под курсором шаблоном не обрабатывается, поэтому вручную.
            DrawWidePoint(self, cusorPos)
    else:
        DrawToolOftenStencil( self, cusorPos, [self.foundGoalSkOut, self.foundGoalSkIn] )
#На самых истоках весь аддон создавался только ради этого инструмента. А то-то вы думаете названия одинаковые.
#Но потом я подахренел от обузданных возможностей, и меня понесло... понесло на создание мейнстримной тройки. Но этого оказалось мало, и теперь инструментов больше чем 7. Чума!
#Дублирующие комментарии есть только здесь (и в целом по убыванию). При спорных ситуациях обращаться к VLT, как к истине в последней инстанции для подражания.
class VoronoiLinkerTool(VoronoiToolDblSk): #Святая святых. То ради чего. Самый первый. Босс всех инструментов. Во славу великому полю расстояния!
    bl_idname = 'node.voronoi_linker'
    bl_label = "Voronoi Linker"
    def NextAssignment(self, context, isBoth):
        if not context.space_data.edit_tree: #Из `modal()` перенесено сюда.
            return
        #В случае не найденного подходящего предыдущий выбор остаётся, отчего не получится вернуть курсор обратно и "отменить" выбор, что очень неудобно.
        self.foundGoalSkIn = None #Поэтому обнуляется каждый раз перед поиском.
        callPos = context.space_data.cursor_location
        for li in GetNearestNodes(context.space_data.edit_tree.nodes, callPos):
            nd = li.tg
            list_fgSksIn, list_fgSksOut = GetNearestSockets(nd, callPos)
            #Этот инструмент триггерится на любой выход
            if isBoth:
                if not self.prefs.vlAnnoyingIgnoring:
                    self.foundGoalSkOut = list_fgSksOut[0] if list_fgSksOut else []
                else:
                    for li in list_fgSksOut:
                        if (not self.isFirstCling)or(CheckAnnoyingIgnore(li.tg)):
                            self.foundGoalSkOut = li
                            break
                    if not self.foundGoalSkOut:
                        continue #todo2 проверить.
            self.isFirstCling = False
            #Получить вход по условиям:
            skOut = self.foundGoalSkOut.tg if self.foundGoalSkOut else None
            if skOut: #Первый заход всегда isBoth=True, однако нод может не иметь выходов.
                #Заметка: нод сокета активации инструмента (isBoth) в любом случае нужно разворачивать.
                #Свёрнутость для рероутов работает, хоть и не отображается визуально; но теперь нет нужды обрабатывать, ибо поддержка свёрнутости введена.
                #Шаблон находится здесь, чтобы нод без выходов не разворачивался.
                if StencilUnCollapseNode(nd, isBoth): #Заметка: isBoth нужен, чтобы нод для SkIn не развернулся раньше, чем задумывалось.
                    #Нужно перерисовывать, если соединилось во вход свёрнутого нода.
                    StencilReNext(self, context, True)
                #На этом этапе условия для отрицания просто найдут другой результат. "Присосётся не к этому, так к другому".
                for li in list_fgSksIn:
                    #Заметка: оператор |= всё равно заставляет вычисляться правый операнд.
                    skIn = li.tg
                    #Для разрешённой-группы-между-собой разрешить "переходы". Рероутом для удобства можно в любой сокет с обеих сторон, минуя различные типы
                    tgl = SkBetweenFieldsCheck(self, skIn, skOut)or( (skOut.node.type=='REROUTE')or(skIn.node.type=='REROUTE') )and(self.prefs.vlReroutesCanInAnyType)
                    #Любой сокет для виртуального выхода; разрешить в виртуальный для любого сокета; обоим в себя запретить
                    tgl = (tgl)or( (skIn.bl_idname=='NodeSocketVirtual')^(skOut.bl_idname=='NodeSocketVirtual') )#or(skIn.bl_idname=='NodeSocketVirtual')or(skOut.bl_idname=='NodeSocketVirtual')
                    #С версии 3.5 новый сокет автоматически не создаётся. Поэтому добавляются новые возможности по соединению
                    tgl = (tgl)or(skIn.node.type=='REROUTE')and(skIn.bl_idname=='NodeSocketVirtual')
                    #Если имена типов одинаковые, но не виртуальные
                    tgl = (tgl)or(skIn.bl_idname==skOut.bl_idname)and( not( (skIn.bl_idname=='NodeSocketVirtual')and(skOut.bl_idname=='NodeSocketVirtual') ) )
                    #Заметка: SkBetweenFieldsCheck() проверяет только меж полями, поэтому явная проверка одинаковости `bl_idname`.
                    if tgl:
                        self.foundGoalSkIn = li
                        break #Обработать нужно только первый ближайший, удовлетворяющий условиям. Иначе результатом будет самый дальний.
                #На этом этапе условия для отрицания сделают результат никаким. Типа "Ничего не нашлось"; и будет обрабатываться соответствующим рисованием.
                if self.foundGoalSkIn:
                    if self.foundGoalSkOut.tg.node==self.foundGoalSkIn.tg.node: #Если для выхода ближайший вход -- его же нод
                        self.foundGoalSkIn = None
                    elif self.foundGoalSkOut.tg.links: #Если выход уже куда-то подсоединён, даже если это выключенные линки.
                        for lk in self.foundGoalSkOut.tg.links:
                            if lk.to_socket==self.foundGoalSkIn.tg: #Если ближайший вход -- один из подсоединений выхода, то обнулить => "желаемое" соединение уже имеется.
                                self.foundGoalSkIn = None
                                #Используемый в проверке выше "self.foundGoalSkIn" обнуляется, поэтому нужно выходить, иначе будет попытка чтения из несуществующего элемента следующей итерацией.
                                break
                    if StencilUnCollapseNode(nd): #"Мейнстримная" обработка свёрнутости.
                        StencilReNext(self, context, False)
            break #Обработать нужно только первый ближайший, удовлетворяющий условиям. Иначе результатом будет самый дальний.
    def modal(self, context, event):
        #context.area.tag_redraw() Неожиданно, но кажется теперь оно перерисовывается само по себе. Но только при каких-то обстоятельствах. Ибо для некоторых инструментов
        # в кастомных деревьях если у нодов нет сокетов.. что-то не работает. #todo1 выяснить подробнее.
        #foundGoalSkIn и foundGoalSkOut как минимум гарантированно обнуляются в шаблоне с isBoth=True
        if StencilMouseNextAndReout(self, context, event, False, True): #Здесь упакован `match event.type:`. Возвращает true, если завершение инструмента.
            if result:=StencilModalEsc(self, context, event):
                return result
            tree = context.space_data.edit_tree
            for nd in tree.nodes:
                if nd.type=='GROUP_INPUT':
                    nd.outputs[-1].hide = self.dict_hideVirtualGpInNodes[nd]
                if nd.type=='GROUP_OUTPUT':
                    nd.inputs[-1].hide = self.dict_hideVirtualGpOutNodes[nd]
            if not( (self.foundGoalSkOut)and(self.foundGoalSkIn) ):
                return {'CANCELLED'}
            sko = self.foundGoalSkOut.tg
            ski = self.foundGoalSkIn.tg
            DoLinkHH(sko, ski) #Самая важная строчка теперь стала высокоуровневой.
            if ski.is_multi_input: #Если мультиинпут, то реализовать адекватный порядок подключения.
                #Моя личная хотелка, которая чинит странное поведение, и делает его логически-корректно-ожидаемым. Накой смысол последние соединённые через api лепятся в начало?
                list_skLinks = []
                for lk in ski.links: #Запомнить все имеющиеся линки по сокетам, и удалить их.
                    list_skLinks.append((lk.from_socket, lk.to_socket))
                    tree.links.remove(lk)
                #До версии 3.5 обработка ниже нужна была, чтобы новый io группы дважды не создавался.
                #Теперь без этой обработки Блендер или крашнется, или линк из виртуального в мультиинпут будет подсвечен красным как "некорректный"
                if sko.bl_idname=='NodeSocketVirtual':
                    sko = sko.node.outputs[-2]
                tree.links.new(sko, ski) #Соединить очередной первым.
                for cyc in range(length(list_skLinks)-1): #Восстановить запомненные. "-1", потому что последний в списке является желанным, что уже соединён строчкой выше.
                    tree.links.new(list_skLinks[cyc][0], list_skLinks[cyc][1])
            RememberLastSockets(sko, ski) #Запомнить сокеты для VRT, которые теперь являются "последними использованными".
            return {'FINISHED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        if result:=StencilBeginToolInvoke(self, context, event):
            return result
        if self.prefs.vlDeselectAllNodes:
            bpy.ops.node.select_all(action='DESELECT') #Возможно так же стоит делать активный нод никаким.
        self.foundGoalSkOut = None
        self.foundGoalSkIn = None
        self.isDrawDoubleNone = True #Метка для CallbackDrawEditTreeIsNone().
        self.dict_hideVirtualGpInNodes = {}
        self.dict_hideVirtualGpOutNodes = {}
        ##
        self.isFirstCling = True #Для CheckAnnoyingIgnore().
        StencilToolWorkPrepare(self, context, CallbackDrawVoronoiLinker, True)
        for nd in context.space_data.edit_tree.nodes: #Выполняется после NA() в шаблоне выше, чтобы к первому присасываться не к виртуальному.
            #К тусовке обработки свёрнутости добавляется моя личная хотелка; ибо виртуальные сокеты я всегда держу скрытыми.
            if nd.type=='GROUP_INPUT':
                self.dict_hideVirtualGpInNodes[nd] = nd.outputs[-1].hide
                nd.outputs[-1].hide = False #Раскрывается у всех сразу, чтобы не страдать головной большую в NA(). #todo1 как-то это не очень. Неплохо было бы придумать что-то по приятнее.
            if nd.type=='GROUP_OUTPUT':
                self.dict_hideVirtualGpOutNodes[nd] = nd.inputs[-1].hide
                nd.inputs[-1].hide = False
        return {'RUNNING_MODAL'}

SmartAddToRegAndAddToKmiDefs(VoronoiLinkerTool, "RIGHTMOUSE_scA")
dict_setKmiCats['g'].add(VoronoiLinkerTool.bl_idname)

set_ndBlidsWithAlphaSk = {'ShaderNodeTexImage', 'GeometryNodeImageTexture', 'CompositorNodeImage', 'ShaderNodeValToRGB', 'CompositorNodeValToRGB'}
def CheckAnnoyingIgnore(sk): #False = игнорировать.
    if sk.node.bl_idname in set_ndBlidsWithAlphaSk:
        return sk.name!="Alpha"# sk!=sk.node.outputs[1]
    return True

set_skTypeFields = {'VALUE', 'RGBA', 'VECTOR', 'INT', 'BOOLEAN', 'ROTATION'} #Так же используют VQMT и VQDT.

#Blid'ы всадников. Так же использует VEST.
set_equestrianPortalBlids = {'NodeGroupInput', 'NodeGroupOutput', 'GeometryNodeSimulationInput', 'GeometryNodeSimulationOutput', 'GeometryNodeRepeatInput', 'GeometryNodeRepeatOutput'}

#"HH" типа значит "High Level", но я с буквой промахнулся D:
def DoLinkHH(sko, ski, isReroutesToAnyType=True, isCanBetweenField=True, isCanFieldToShader=True): #Какое неожиданное визуальное совпадение с порядковым номером "sk0" "sk1".
    #Коль мы теперь высокоуровневые, можем использоваться независимо, придётся суетиться с особыми случаями:
    if not(sko and ski): #Они должны быть.
        return
    if sko.id_data!=ski.id_data: #Они должны быть в одном мире.
        return
    if not(sko.is_output^ski.is_output): #Они должны быть разного гендера.
        return
    if not sko.is_output: #Вывод должен быть первым.
        sko, ski = ski, sko
    #Заметка: "высокоуровневый", но не для глупых юзеров; соединяться между виртуальными можно, чорт возьми.
    tree = sko.id_data
    if tree.bl_idname=='NodeTreeUndefined': #Дерево не должно быть потерянным.
        return #В потерянном дереве сокеты вручную соединяются, а через api нет. Так что выходим.
    if sko.node==ski.node: #Для одного и того же нода всё очевидно бессмысленно, пусть и возможно. Более актуально для интерфейсов.
        return
    isSkoField = sko.type in set_skTypeFields
    isSkoNdReroute = sko.node.type=='REROUTE'
    isSkiNdReroute = ski.node.type=='REROUTE'
    isSkoVirtual = (sko.bl_idname=='NodeSocketVirtual')and(not isSkoNdReroute) #Виртуальный актуален только для интерфейсов, нужно исключить "рероута-самозванца".
    isSkiVirtual = (ski.bl_idname=='NodeSocketVirtual')and(not isSkiNdReroute) #Заметка: virtual type и аддонские сокеты одинаковы.
    #Можно, если
    if not( (isReroutesToAnyType)and( (isSkoNdReroute)or(isSkiNdReroute) ) ): #Хотя бы один из них рероут
        if not( (sko.type==ski.type)or( (isCanBetweenField)and(isSkoField)and(ski.type in set_skTypeFields) ) ): #Одинаковый по типу или между полями
            if not( (isCanFieldToShader)and(isSkoField)and(ski.type=='SHADER') ): #Поле в шейдер
                if not( isSkoVirtual or isSkiVirtual ): #Кто-то из них виртуальный (для интерфейсов).
                    return None #Низя между текущими типами.
    #Отсеивание некорректных завершено. Теперь интерфейсы:
    ndo = sko.node
    ndi = ski.node
    procIface = True
    #Для суеты с интерфейсами требуется только один виртуальный. Если их нет, то обычное соединение.
    #Но если они оба виртуальные, читать информацию не от кого; от чего суета с интерфейсами бесполезна.
    if not( isSkoVirtual^isSkiVirtual ): #Два условия упакованы в один xor.
        procIface = False
    elif ndo.type==ndi.type=='REROUTE': #Между рероутами гарантированно связь. Этакий мини-островок безопасности, затишье пере бурей.
        procIface = False
    elif not( (ndo.bl_idname in set_equestrianPortalBlids)or(ndi.bl_idname in set_equestrianPortalBlids) ): #Хотя бы один из нодов должен быть всадником.
        procIface = False
    if procIface: #Что ж, бурая оказалось не такой уж и бурей. Я ожидал больший спагетти-код. Как всё легко и ясно получается, если мозги-то включить.
        #Получить нод всадника виртуального сокета
        ndEq = ndo if isSkoVirtual else ndi #Исходим из того, что всадник вывода равновероятен со своим компаньоном.
        #Коллапсируем рамочных всадников сразу же
        ndEq = getattr(ndEq,'paired_output', ndEq)
        #Интересно, где-нибудь в параллельной вселенной существуют виртуальные мультиинпуты?.
        skTar = sko if isSkiVirtual else ski
        match ndEq.bl_idname:
            case 'NodeGroupOutput': typeEq = 0
            case 'NodeGroupInput':  typeEq = 1
            case 'GeometryNodeSimulationOutput': typeEq = 2
            case 'GeometryNodeRepeatOutput':     typeEq = 3
        #Неподдерживаемых всадником не обрабатывать
        can = True
        match typeEq:
            case 2: can = skTar.type in {'VALUE','INT','BOOLEAN','VECTOR','ROTATION','STRING','RGBA','GEOMETRY'}
            case 3: can = skTar.type in {'VALUE','INT','BOOLEAN','VECTOR','ROTATION','STRING','RGBA','OBJECT','IMAGE','GEOMETRY','COLLECTION','MATERIAL'}
        if not can:
            return None
        #Создать интерфейс
        match typeEq:
            case 0|1:
                NewSkfFromSk(tree, not typeEq, skTar)
            case 2|3:
                ( ndEq.state_items if typeEq==2 else ndEq.repeat_items ).new({'VALUE':'FLOAT'}.get(skTar.type,skTar.type), GetSkLabelName(skTar))
        #Перевыбрать для нового появившегося сокета
        if isSkiVirtual:
            ski = ski.node.inputs[-2]
        else:
            sko = sko.node.outputs[-2]
    #Путешествие успешно выполнено. Наконец-то переходим к самому главному:
    def DoLinkLL(tree, sko, ski):
        return tree.links.new(sko, ski) #hi.
    return DoLinkLL(tree, sko, ski)
    #Заметка: С версии Blender 3.5 виртуальные инпуты теперь можут принимать в себя прям как мультиинпуты.
    # Они даже могут между собой по нескольку раз соединяться, офигеть. Разрабы "отпустили", так сказать, в свободное плаванье.

def CallbackDrawVoronoiPreview(self, context):
    if StencilStartDrawCallback(self, context):
        return
    cusorPos = context.space_data.cursor_location
    if self.foundGoalSkOut:
        if self.prefs.vpRvEeSksHighlighting: #Помощь в реверс-инженеринге, подсвечивать места соединения, и отображать имя этих сокетов, одновременно.
            #Определить масштаб для надписей:
            pos = VecWorldToRegScale(cusorPos, self)
            loc = Vector(cusorPos.x+6*1000, cusorPos.y)
            rd = (VecWorldToRegScale(loc, self)[0]-pos[0])/1000
            #Нарисовать:
            ndTar = self.foundGoalSkOut.tg.node
            for side in [False, True]:
                for skTar in ndTar.outputs if side else ndTar.inputs:
                    for lk in skTar.links:
                        if not lk.is_muted:
                            sk = lk.to_socket if side else lk.from_socket
                            nd = sk.node
                            nd.hide = False #Запись во время рисования. По крайней мере не так как сильно, как в MassLinker Tool.
                            if nd.type!='REROUTE': #if (not nd.hide)and(nd.type!='REROUTE'): #Отображать у тех, кто не свёрнут и не рероут.
                                list_fgSks = GetFromIoPuts(nd, 1-(side*2), cusorPos)
                                for li in list_fgSks:
                                    if li.tg==sk:
                                        DrawToolOftenStencil( self, cusorPos, [li], isDrawText=False, isDrawOnlyArea=True )
                                        DrawSkText( self, li.pos, ((li.tg.is_output*2-1), -0.5), li, min(rd*4,25) )
                                        break
        #Порядок рисования важен, главное над реверс-инженерингом.
        DrawToolOftenStencil( self, cusorPos, [self.foundGoalSkOut], isLineToCursor=True, textSideFlip=True, isDrawText=True, isDrawMarkersMoreTharOne=True )
    elif self.prefs.dsIsDrawPoint:
        DrawWidePoint(self, cusorPos)
class VoronoiPreviewTool(VoronoiToolSk):
    bl_idname = 'node.voronoi_preview'
    bl_label = "Voronoi Preview"
    isSelectingPreviewedNode: bpy.props.BoolProperty(name="Select previewed node",  default=True)
    isTriggerOnlyOnLink:      bpy.props.BoolProperty(name="Trigger only on linked", default=False) #Изначально часть возможностей реверсинженеринга.
    isEqualAnchorType:        bpy.props.BoolProperty(name="Equal anchor type",      default=False)
    def NextAssignment(self, context, *naArgs):
        tree = context.space_data.edit_tree
        if not tree:
            return
        isGeoTree = tree.bl_idname=='GeometryNodeTree'
        if False:
            #Уж было я добавил возможность сосаться к полям для виевера, но потом понял, что нет api на смену его типа предпросмотра. Опять. Придётся хранить на низком старте.
            isGeoViewer = False #Для присасывания к полям для ГеоВиевеера.
            if isGeoTree:
                for nd in tree.nodes:
                    if nd.type=='VIEWER':
                        isGeoViewer = True
                        break
        rrAnch = tree.nodes.get(voronoiAnchorName) #Если в геонодах есть якорь, то триггериться не только на геосокеты.
        #Некоторые пользователи в "начале знакомства" с инструментом захотят переименовать якорь.
        #Каждый призыв якоря одинаков по заголовку, а при повторном призыве заголовок всё равно меняется обратно на стандартный.
        #После чего пользователи поймут, что переименовывать якорь бесполезно.
        if rrAnch: #Эта проверка с установкой лишь ускоряет процесс осознания.
            rrAnch.label = voronoiAnchorName
        isAncohorExist = not not rrAnch
        self.foundGoalSkOut = None #Нет нужды, но сбрасывается для ясности картины. Было полезно для отладки.
        callPos = context.space_data.cursor_location
        for li in GetNearestNodes(tree.nodes, callPos):
            nd = li.tg
            if self.prefs.vpRvEeIsSavePreviewResults:
                #Игнорировать готовый нод для переименования и тем самым сохраняя результаты предпросмотра.
                if nd.name==voronoiPreviewResultNdName:
                    continue
            #Если в геометрических нодах, то игнорировать ноды без выходов геометрии
            if (isGeoTree)and(not isAncohorExist):
                if not [True for sk in nd.outputs if (sk.type=='GEOMETRY')and(not sk.hide)and(sk.enabled)]: #Искать сокеты геометрии, которые видимы.
                    continue
            #Пропускать ноды если визуально нет сокетов; или есть, но только виртуальные. Для рероутов всё бесполезно.
            if (not [True for sk in nd.outputs if (not sk.hide)and(sk.enabled)and(sk.bl_idname!='NodeSocketVirtual')])and(nd.type!='REROUTE'):
                continue
            #Всё выше нужно было для того, чтобы точка не висела просто так и нод не мешал для удобного использования инструмента. По ощущениям получаются как "прозрачные" ноды.
            #Игнорировать свой собственный спец-рероут-якорь (проверка на тип и имя)
            if ( (nd.type=='REROUTE')and(nd.name==voronoiAnchorName) ):
                continue
            #В случае успеха переходить к сокетам:
            list_fgSksOut = GetNearestSockets(nd, callPos)[1]
            for li in list_fgSksOut:
                #Игнорировать свои сокеты мостов здесь. Нужно для нод нодгрупп, у которых "торчит" сокет моста и к которому произойдёт присасывание без этой проверки; и после чего они будут удалены в PreviewFromSk().
                if li.tg.name==voronoiSkPreviewName:
                    continue
                #Этот инструмент триггерится на любой выход кроме виртуального. В геометрических нодах искать только выходы геометрии.
                #Якорь притягивает на себя превиев; рероут может принимать любой тип; следовательно -- при наличии якоря отключать триггер только на геосокеты
                if (li.tg.bl_idname!='NodeSocketVirtual')and( (not isGeoTree)or(li.tg.type=='GEOMETRY')or(isAncohorExist) ):
                    can = True
                    if isAncohorExist: #EqualAnchorType.
                        rrSkBlId = rrAnch.outputs[0].bl_idname
                        can = (not self.isEqualAnchorType)or(li.tg.bl_idname==rrSkBlId)or(rrSkBlId=='NodeSocketVirtual')
                    if can:
                        if (not(self.isTriggerOnlyOnLink))or(li.tg.is_linked): #Помощь в реверс-инженеринге, триггериться только на существующие линки. Ускоряет процесс "считывания/понимания" дерева.
                            self.foundGoalSkOut = li
                            break
            if self.foundGoalSkOut: #Завершать в случае успеха. Иначе, например для игнорирования своих сокетов моста, если у нода только они -- остановится рядом и не найдёт других.
                break
        if self.foundGoalSkOut:
            if self.prefs.vpIsLivePreview:
                try:
                    PreviewFromSk(self, context, self.foundGoalSkOut.tg)
                except: #todo4 придумать что делать с ошибками в NA() во всех инструментах.
                    pass
            if self.prefs.vpRvEeIsColorOnionNodes: #Помощь в реверс-инженеринге, вместо поиска глазами тоненьких линий, быстрое визуальное считывание связанных нод топологией.
                for nd in tree.nodes:
                    nd.use_custom_color = False #Не париться с запоминанием последних и тупо выключать у всех каждый раз. Дёшево и сердито.
                for sk in self.foundGoalSkOut.tg.node.inputs:
                    for lk in sk.links:
                        nd = lk.from_socket.node
                        nd.use_custom_color = True
                        if nd.name!=voronoiPreviewResultNdName:
                            nd.color = (0.55, 0.188, 0.188)
                        nd.hide = False #А так же раскрывать их.
                for sk in self.foundGoalSkOut.tg.node.outputs:
                    for lk in sk.links:
                        nd = lk.to_socket.node
                        nd.use_custom_color = True
                        if nd.name!=voronoiPreviewResultNdName: #Нод для сохранения результата не перекрашивать
                            nd.color = (0.188, 0.188, 0.5)
                        nd.hide = False #А так же раскрывать их.
            StencilUnCollapseNode(self.foundGoalSkOut.tg.node)
    def modal(self, context, event):
        if StencilMouseNextAndReout(self, context, event):
            if result:=StencilModalEsc(self, context, event):
                return result
            if not self.foundGoalSkOut:
                return {'CANCELLED'}
            PreviewFromSk(self, context, self.foundGoalSkOut.tg)
            RememberLastSockets(self.foundGoalSkOut.tg, None)
            if self.prefs.vpRvEeIsColorOnionNodes:
                for nd in context.space_data.edit_tree.nodes:
                    dv = self.dict_saveRestoreNodeColors.get(nd, None) #Так же, как и в восстановлении свёрнутости.
                    if dv is not None:
                        nd.use_custom_color = dv[0]
                        nd.color = dv[1]
            return {'FINISHED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        if result:=UselessForCustomUndefTrees(context):
            return result
        if result:=StencilBeginToolInvoke(self, context, event):
            return result
        #Если использование классического viewer'а разрешено, завершить инструмент с меткой пропуска, "передавая эстафету" оригинальному виеверу.
        match context.space_data.tree_type:
            case 'CompositorNodeTree':
                if (self.prefs.vpAllowClassicCompositorViewer)and('FINISHED' in bpy.ops.node.select('INVOKE_DEFAULT')):
                    return {'PASS_THROUGH'}
            case 'GeometryNodeTree':
                if (self.prefs.vpAllowClassicGeoViewer)and('FINISHED' in bpy.ops.node.select('INVOKE_DEFAULT')):
                    return {'PASS_THROUGH'}
        self.foundGoalSkOut = None
        if self.prefs.vpRvEeIsColorOnionNodes:
            #Запомнить все цвета, и обнулить их всех.
            self.dict_saveRestoreNodeColors = {}
            for nd in context.space_data.edit_tree.nodes:
                self.dict_saveRestoreNodeColors[nd] = (nd.use_custom_color, nd.color.copy()) #todo0 Алерт x2(x4) комбо. Погружаться в С++.
                nd.use_custom_color = False
            #Заметка: ноды сохранения результата с луковичными цветами обрабатываются как есть естественным образом. Дублированный(aka сохранённый) нод не будет оставаться незатрагиваемым.
        StencilToolWorkPrepare(self, context, CallbackDrawVoronoiPreview)
        return {'RUNNING_MODAL'}
#Вынесено в отдельный инструмент, потому что уж больно слишком разные; да и ныне несуществующий '.isPlaceAnAnchor' мозолил глаза своим True-наличием и => бесполезностью всех остальных.
#А так же задел на будущее для потенциальных мультиякорей, чтобы всё это не превращалось в спагетти-код.
class VoronoiPreviewAnchorTool(VoronoiTool):
    bl_idname = 'node.voronoi_preview_anchor'
    bl_label = "Voronoi Preview Anchor"
    def execute(self, context):
        if result:=UselessForCustomUndefTrees(context, isForCustom=False):
            return result
        #Заметка: единственный доступный 'isPassThrough' поддерживается на половину. Если в kmi не указано, то через ForseSetSelfNonePropToDefault() не установить -- event'а нет.
        if StencilProcPassThrought(self, context):
            return {'PASS_THROUGH'}
        tree = context.space_data.edit_tree
        if not tree:
            return {'CANCELLED'}
        for nd in tree.nodes:
            nd.select = False
        rrAnch = tree.nodes.get(voronoiAnchorName)
        tgl = not rrAnch #Метка для обработки при первом появлении.
        rrAnch = rrAnch or tree.nodes.new('NodeReroute')
        tree.nodes.active = rrAnch
        rrAnch.name = voronoiAnchorName
        rrAnch.label = rrAnch.name
        rrAnch.location = context.space_data.cursor_location
        rrAnch.select = True
        if tgl:
            #Почему бы и нет. Зато красивый.
            rrAnch.inputs[0].type = 'MATERIAL' #Для аддонских деревьев, потому что в них "напролом" ниже не работает.
            rrAnch.outputs[0].type = rrAnch.inputs[0].type #Чтобы цвет выхода у линка был таким же.
            #Выше установка напрямую 'CUSTOM' не работает, поэтому идём напролом (спасибо обновлению Blender 3.5):
            nd = tree.nodes.new('NodeGroupInput')
            tree.links.new(nd.outputs[-1], rrAnch.inputs[0])
            tree.nodes.remove(nd)
        return {'FINISHED'}

SmartAddToRegAndAddToKmiDefs(VoronoiPreviewTool,       "LEFTMOUSE_SCa")
SmartAddToRegAndAddToKmiDefs(VoronoiPreviewAnchorTool, "RIGHTMOUSE_SCa")
dict_setKmiCats['g'].add(VoronoiPreviewTool.bl_idname)
dict_setKmiCats['g'].add(VoronoiPreviewAnchorTool.bl_idname)

class WayTree:
    def __init__(self, tree=None, nd=None):
        self.tree = tree
        self.nd = nd
        self.isCorrect = None #Целевой глубине не с кем сравнивать.
        self.isUseExtAndSkPr = None #Оптимизация для чистки.
        self.prLink = None #Для более адекватной организации для RvEe.
def GetTreesPath(context, nd):
    list_path = [ WayTree(pt.node_tree, pt.node_tree.nodes.active) for pt in context.space_data.path ]
    #Как я могу судить, сама суть реализации редактора узлов не хранит >нод<, через который пользователь зашёл в группу (но это не точно).
    #Поэтому если активным оказалась не нод-группа, то заменить на первый найденный-по-группе нод (или ничего, если не найдено)
    for curWy, upWy in zip(list_path, list_path[1:]):
        if (not curWy.nd)or(curWy.nd.type!='GROUP')or(curWy.nd.node_tree!=upWy.tree): #Определить отсутствие связи между глубинами.
            curWy.nd = None #Избавиться от текущего неправильного. Уж лучше останется никакой.
            for nd in curWy.tree.nodes:
                if (nd.type=='GROUP')and(nd.node_tree==upWy.tree): #Если в текущей глубине с неправильным нодом имеется нод группы с правильной группой.
                    curWy.nd = nd
                    break #Починка этой глубины успешно завершена.
        curWy.isCorrect = curWy.nd==upWy.tree #По факту.
    return list_path

def GetRootNd(tree):
    match tree.bl_idname:
        case 'ShaderNodeTree':
            for nd in tree.nodes:
                if (nd.type in {'OUTPUT_MATERIAL','OUTPUT_WORLD','OUTPUT_LIGHT','OUTPUT_LINESTYLE','OUTPUT'})and(nd.is_active_output):
                    return nd
        case 'GeometryNodeTree':
            if False:
                #Для очередных глубин тоже актуально получать пересасывание сразу в ввиевер, но см. |6|; текущий конвеер логически не приспособлен для этого.
                #Поэтому больше не поддерживается, ибо "решено" только на половину. Так что старый добрый якорь в помощь.
                for nd in reversed(tree.nodes): #Активный виевер будет в конце списка, так что искать с конца.
                    if nd.type=='VIEWER':
                        if [True for sk in nd.inputs[1:] if sk.links]: #Выбирать виевер только если у него есть линк для просмотра поля.
                            return nd
                        break #Обрабатывать только первый попавшийся ! виевер; он же активный. Потому что иначе будет некомфортное поведение для нескольких виеверов.
            for nd in tree.nodes:
                if (nd.type=='GROUP_OUTPUT')and(nd.is_active_output):
                    for sk in nd.inputs:
                        if sk.type=='GEOMETRY':
                            return nd
        case 'CompositorNodeTree':
            for nd in tree.nodes:
                if nd.type=='VIEWER':
                    return nd
            for nd in tree.nodes:
                if nd.type=='COMPOSITE':
                    return nd
        case 'TextureNodeTree':
            for nd in tree.nodes:
                if nd.type=='OUTPUT':
                    return nd
    return None
def GetRootSk(tree, ndRoot, targetSk):
    match tree.bl_idname:
        case 'ShaderNodeTree':
            return ndRoot.inputs[ (targetSk.name=="Volume")*(ndRoot.type in {'OUTPUT_MATERIAL','OUTPUT_WORLD'}) ]
        case 'GeometryNodeTree':
            for sk in ndRoot.inputs:
                if sk.type=='GEOMETRY':
                    return sk
    return ndRoot.inputs[0] #Заметка: здесь так же окажется неудачный от GeometryNodeTree выше.

featureUsingExistingPath = True
#Заметка: интерфейсы симуляции и зоны повторения не рассматривать, их обработка потребует поиска по каждому ноду в дерве, отчего будет Big(O) алерт.
def DoPreview(context, targetSk):
    def NewLostNode(txt_type, ndTar=None):
        ndNew = tree.nodes.new(txt_type)
        if ndTar:
            ndNew.location = ndTar.location
            ndNew.location.x += ndTar.width*2
        return ndNew
    def GetSkFromIdf(io, idf):
        for sk in io:
            if sk.identifier==idf:
                return sk
        return None
    list_way = GetTreesPath(context, targetSk.node)
    higWay = length(list_way)-1
    list_way[higWay].nd = targetSk.node #Подразумеваемым гарантией-конвеером глубин заходов целевой не обрабатывается, поэтому указывать явно. (Незабыть перевести с эльфийского на русский)
    ##
    previewSkType = "RGBA" #Цвет, а не шейдер -- потому что иногда есть нужда вставить нод куда-то в пути превиева.
    #Но если линки шейдерные -- готовьтесь к разочарованию. Поэтому цвет (кой и был изначально у NW).
    isGeoTree = list_way[0].tree.bl_idname=='GeometryNodeTree'
    if isGeoTree:
        previewSkType = "GEOMETRY"
    elif targetSk.type=='SHADER':
        previewSkType = "SHADER"
    idLastSkEx = '' #Для featureUsingExistingPath.
    def GetBridgeSk(ioputs):
        sk = ioputs.get(voronoiSkPreviewName)
        if (sk)and(sk.type!=previewSkType):
            ViaVerSkfRemove(tree, True, ViaVerGetSkf(tree, True, voronoiSkPreviewName))
            return None
        return sk
    def GetTypeSkfBridge():
        match previewSkType:
            case 'GEOMETRY': return "NodeSocketGeometry"
            case 'SHADER':   return "NodeSocketShader"
            case 'RGBA':     return "NodeSocketColor"
    for cyc in reversed(range(higWay+1)):
        curWay = list_way[cyc]
        tree = curWay.tree
        #Определить отправляющий нод:
        portalNdFrom = curWay.nd #targetSk.node уже включён в путь для cyc==higWay.
        isCreatedNgOut = False
        if not portalNdFrom:
            portalNdFrom = tree.nodes.new(tree.bl_idname.replace("Tree","Group"))
            portalNdFrom.node_tree = list_way[cyc+1].tree
            isCreatedNgOut = True #Чтобы установить позицию нода от принимающего нода, который сейчас неизвестен.
        #Определить принимающий нод:
        portalNdTo = None
        if not cyc: #Корень.
            portalNdTo = GetRootNd(tree)
            if not portalNdTo:
                #"Визуальное оповещение", что соединяться некуда. Можно было бы и вручную добавить, но лень шататься с принимающими нодами ShaderNodeTree'а.
                portalNdTo = NewLostNode('NodeReroute', portalNdFrom)
        else: #Очередная глубина.
            for nd in tree.nodes:
                if (nd.type=='GROUP_OUTPUT')and(nd.is_active_output):
                    portalNdTo = nd
                    break
            if not portalNdTo:
                #Создать вывод группы самостоятельно, вместо того чтобы остановиться и не знать что делать.
                portalNdTo = NewLostNode('NodeGroupOutput', portalNdFrom)
        if isGeoTree:
            #Теперь поведение наличия виевера похоже на якорь.
            for nd in tree.nodes:
                if nd.type=='VIEWER':
                    portalNdTo = nd
                    break
        if isCreatedNgOut:
            portalNdFrom.location = portalNdTo.location-Vector(portalNdFrom.width+40, 0)
        #Определить отправляющий сокет:
        portalSkFrom = None
        if (featureUsingExistingPath)and(idLastSkEx):
            portalSkFrom = GetSkFromIdf(portalNdFrom.outputs, idLastSkEx)
            idLastSkEx = '' #Важно обнулять. Выбранный сокет может не иметь линков или связи до следующего портала, отчего на следующей глубине будут несоответствия.
        if not portalSkFrom:
            portalSkFrom = targetSk if cyc==higWay else GetBridgeSk(portalNdFrom.outputs)
        #Определить принимающий сокет:
        portalSkTo = None
        if (isGeoTree)and(portalNdTo.type=='VIEWER'):
            portalSkTo = portalNdTo.inputs[0]
        if (not portalSkTo)and(featureUsingExistingPath)and(cyc): #Имеет смысл записывать для не-корня.
            #Моё улучшающее изобретение -- если соединение уже имеется, то зачем создавать рядом такое же?.
            #Это эстетически комфортно, а так же помогает отчистить последствия предпросмотра не выходя из целевой глубины (добавлены условия, см. чистку).
            for lk in portalSkFrom.links:
                #Поскольку интерфейсы не удаляются, вместо мейнстрима ниже он заполучится отсюда (и результат будет таким же), поэтому вторая проверка для isUseExtAndSkPr.
                if (lk.to_node==portalNdTo)and(lk.to_socket.name!=voronoiSkPreviewName):
                    portalSkTo = lk.to_socket
                    idLastSkEx = portalSkTo.identifier #Выходы нода нодгруппы и входы выхода группы совпадают. Сохранить информацию для следующей глубины продолжения.
                    curWay.isUseExtAndSkPr = GetBridgeSk(portalNdTo.inputs) #Для чистки. Если будет без линков, то удалять. При чистке они не ищутся по факту, потому что Big(O).
        if not portalSkTo: #Основной мейнстрим получения.
            portalSkTo = GetRootSk(tree, portalNdTo, targetSk) if not cyc else GetBridgeSk(portalNdTo.inputs) #|6|.
        if (not portalSkTo)and(cyc): #Очередные глубины -- всегда группы, для них и нужно генерировать skf. Проверка на cyc не обязательна, сокет с корнем (из-за рероута) всегда будет.
            #Если выше не смог получить сокет от входов нода нод группы, то и интерфейса-то тоже нет. Поэтому проверка `not tree.outputs.get(voronoiSkPreviewName)` без нужды.
            ViaVerNewSkf(tree, True, GetTypeSkfBridge(), voronoiSkPreviewName).hide_value = True
            portalSkTo = GetBridgeSk(portalNdTo.inputs) #Перевыбрать новосозданный.
        #Соединить:
        ndAnchor = tree.nodes.get(voronoiAnchorName)
        if ndAnchor: #Якорь делает "планы изменились", и пересасывает поток на себя.
            lk = tree.links.new(portalSkFrom, ndAnchor.inputs[0])
            #tree.links.new(ndAnchor.outputs[0], portalSkTo) #todo3 посмотреть, что из этого можно сделать.
            break #Завершение после напарывания повышает возможности использования якоря, делая его ещё круче. Если у вас течка от Voronoi_Anchor, то я вас понимаю. У меня тоже.
            #Завершение позволяет иметь пользовательское соединение от глубины с якорем и до корня, не разрушая их.
        elif (portalSkFrom)and(portalSkTo): #Иначе обычное соединение маршрута.
            lk = tree.links.new(portalSkFrom, portalSkTo)
        curWay.prLink = lk
    return list_way
def PreviewFromSk(self, context, targetSk):
    if (not targetSk)or(not targetSk.is_output):
        return
    list_way = DoPreview(context, targetSk)
    #Гениально я придумал удалять интерфейсы после предпросмотра; стало возможным благодаря не-удалению в контекстных путях. Теперь ими можно будет пользоваться более свободно.
    tree = context.space_data.edit_tree
    if (True)or(not tree.nodes.get(voronoiAnchorName)): #'True' см. далее.
        #Если в текущем дереве есть якорь, то никаких voronoiSkPreviewName не удалять; благодаря чему становится доступным ещё одно особое использование инструмента.
        #Должно было стать логическим продолжением после "завершение после напарывания", но допёр до этого только сейчас.
        #P.s. Я забыл нахрен какое. А теперь они не удаляются от контекстных путей, так что информация уже утеряна D:
        dict_treeNExt = dict({(wy.tree, wy.isUseExtAndSkPr) for wy in list_way})
        dict_treeOrder = dict({(wy.tree, cyc) for cyc, wy in enumerate(reversed(list_way))}) #Путь имеет линки, середине не узнать о хвосте, поэтому из текущей глубины до корня, чтобы "каскадом" корректно обработалось.
        for ng in sorted(bpy.data.node_groups, key=lambda a: dict_treeOrder.get(a,-1)):
            #Удалить все свои следы предыдущего использования инструмента для всех нод-групп, чей тип текущего редактора такой же.
            if ng.bl_idname==tree.bl_idname:
                #Но не удалять мосты для деревьев контекстного пути (удалять, если их сокеты пустые).
                sk = dict_treeNExt.get(ng, None) #Для Ctrl-F: isUseExtAndSkPr используется здесь.
                if (ng not in dict_treeNExt)or((not sk.links) if sk else None)or( (ng==tree)and(sk) ):
                    sk = True
                    while sk: #Ищется по имени. Пользователь может сделать дубликат, от чего без while они будут исчезать по одному каждую активацию предпросмотра.
                        sk = ViaVerGetSkf(ng, True, voronoiSkPreviewName)
                        if sk:
                            ViaVerSkfRemove(ng, True, sk)
    if self.isSelectingPreviewedNode:
        NdSelectAndActive(targetSk.node)
    if self.prefs.vpRvEeIsSavePreviewResults: #Помощь в реверс-инженеринге, сохранять текущий сокет просмотра для последующего "менеджмента".
        def GetTypeOfNodeSave(sk):
            match sk.type:
                case 'GEOMETRY': return 2
                case 'SHADER': return 1
                case _: return 0
        prLink = list_way[length(list_way)-1].prLink
        idSkSave = GetTypeOfNodeSave(prLink.from_socket)
        vec = prLink.to_node.location
        vec = [vec[0]+prLink.to_node.width+40, vec[1]]
        ndReSave = tree.nodes.get(voronoiPreviewResultNdName)
        if ndReSave:
            if ndReSave.label!=voronoiPreviewResultNdName:
                ndReSave.name += "_"+ndReSave.label
                ndReSave = None
            elif GetTypeOfNodeSave(ndReSave.outputs[0])!=idSkSave: #Если это нод от другого типа сохранения
                vec = ndReSave.location.copy() #При смене типа сохранять позицию "активного" нода-сохранения. Заметка: не забывать про .copy(), потому что далее нод удаляется.
                tree.nodes.remove(ndReSave)
                ndReSave = None
        if not ndReSave:
            match idSkSave:
                case 0: txt = "MixRGB" #"MixRGB" потому что он есть во всех редакторах; а ещё Shift+G > Type.
                case 1: txt = "AddShader"
                case 2: txt = "SeparateGeometry"
            ndReSave = tree.nodes.new(tree.bl_idname.replace("Tree","")+txt)
            ndReSave.location = vec
        ndReSave.name = voronoiPreviewResultNdName
        ndReSave.select = False
        ndReSave.label = ndReSave.name
        ndReSave.use_custom_color = True
        match idSkSave: #Разукрасить нод сохранения.
            case 0:
                ndReSave.color = (0.42968, 0.42968, 0.113725)
                ndReSave.show_options = False
                ndReSave.blend_type = 'ADD'
                ndReSave.inputs[0].default_value = 0
                ndReSave.inputs[1].default_value = (0.155927, 0.155927, 0.012286, 1.0)
                ndReSave.inputs[2].default_value = ndReSave.inputs[1].default_value #Немного лишнее.
                ndReSave.inputs[0].hide = True
                ndReSave.inputs[1].name = "Color"
                ndReSave.inputs[2].hide = True
                inx = 1
            case 1:
                ndReSave.color = (0.168627, 0.395780, 0.168627)
                ndReSave.inputs[1].hide = True
                inx = 0
            case 2:
                ndReSave.color = (0.113725, 0.447058, 0.368627)
                ndReSave.show_options = False
                ndReSave.inputs[1].hide = True
                ndReSave.outputs[0].name = "Geometry"
                ndReSave.outputs[1].hide = True
                inx = 0
        tree.links.new(prLink.from_socket, ndReSave.inputs[inx])
        tree.links.new(ndReSave.outputs[0], prLink.to_socket)

class MixerData:
    sk0 = None
    sk1 = None
    skType = ""
    isHideOptions = False
    isPlaceImmediately = False
    isSpeedPie = False
    pieScale = 0
    pieDisplaySocketTypeInfo = 0
    pieAlignment = 0
mxData = MixerData()

txt_noMixingOptions = "No mixing options"
def DrawMixerSkText(self, cusorPos, fg, ofsY, facY): #Вынесено вовне, чтобы этим мог воспользоваться VST.
    txtDim = DrawSkText( self, cusorPos, (self.prefs.dsDistFromCursor*(fg.tg.is_output*2-1), ofsY), fg )
    if (fg.tg.links)and(self.prefs.dsIsDrawMarker):
        DrawIsLinkedMarker( self, cusorPos, [txtDim[0]*(fg.tg.is_output*2-1), txtDim[1]*facY*0.75], GetSkCol(fg.tg) )
def CallbackDrawVoronoiMixer(self, context):
    if StencilStartDrawCallback(self, context):
        return
    cusorPos = context.space_data.cursor_location
    if self.foundGoalSkOut0:
        DrawToolOftenStencil( self, cusorPos, [self.foundGoalSkOut0], isLineToCursor=True, isDrawText=False )
        tgl = not not self.foundGoalSkOut1
        DrawMixerSkText(self, cusorPos, self.foundGoalSkOut0, -0.5+0.75*tgl, int(tgl))
        if tgl:
            DrawToolOftenStencil( self, cusorPos, [self.foundGoalSkOut1], isLineToCursor=True, isDrawText=False )
            DrawMixerSkText(self, cusorPos, self.foundGoalSkOut1, -1.25, -1)
    elif self.prefs.dsIsDrawPoint:
        DrawWidePoint(self, cusorPos)
class VoronoiMixerTool(VoronoiToolDblSk):
    bl_idname = 'node.voronoi_mixer'
    bl_label = "Voronoi Mixer"
    isCanFromOne:       bpy.props.BoolProperty(name="Can from one socket", default=True) #Стоит первым, чтобы быть похожим на VQMT в kmi.
    isHideOptions:      bpy.props.BoolProperty(name="Hide node options",   default=False)
    isPlaceImmediately: bpy.props.BoolProperty(name="Place immediately",   default=False) #todo3 возможно стоит добавить промежуточный вариант, где отмена приведёт не к удалению, а к отмене перемещения.
    def NextAssignment(self, context, isBoth):
        if not context.space_data.edit_tree:
            return
        if isBoth:
            self.foundGoalSkOut0 = None #Нужно обнулять из-за наличия двух continue ниже.
        self.foundGoalSkOut1 = None
        callPos = context.space_data.cursor_location
        isBothSucessSwitch = True #Изначально был создан в VQMT. Нужен, чтобы повторно не перевыбирать уже успешный isBoth, если далее для второго сокета была лажа и цикл по нодам продолжился..
        #todo1 Возможно стоит иметь два NextAssignment()'а вместо isBoth'а; но это не точно.
        for li in GetNearestNodes(context.space_data.edit_tree.nodes, callPos):
            nd = li.tg
            StencilUnCollapseNode(nd, isBoth)
            list_fgSksOut = GetNearestSockets(nd, callPos)[1]
            if not list_fgSksOut:
                continue
            #В фильтре нод нет нужды.
            #Этот инструмент триггерится на любой выход (ныне кроме виртуальных) для первого.
            if (isBoth)and(isBothSucessSwitch):
                for li in list_fgSksOut:
                    self.foundGoalSkOut0 = li
                    break
            isBothSucessSwitch = not self.foundGoalSkOut0 #Чтобы не раскрывал все ноды в дереве.
            #Для второго по условиям:
            skOut0 = self.foundGoalSkOut0.tg if self.foundGoalSkOut0 else None
            if skOut0:
                for li in list_fgSksOut:
                    skOut1 = li.tg
                    orV = (skOut1.bl_idname=='NodeSocketVirtual')or(skOut0.bl_idname=='NodeSocketVirtual')
                    #Заметка: к VQMT такие возможности не относятся. Ибо он только по полям. Было бы странно присасываться ещё и к виртуальным.
                    tgl = (skOut1.bl_idname=='NodeSocketVirtual')^(skOut0.bl_idname=='NodeSocketVirtual')
                    tgl = (tgl)or( SkBetweenFieldsCheck(self, skOut0, skOut1)or( (skOut1.bl_idname==skOut0.bl_idname)and(not orV) ) )
                    tgl = (tgl)or( (skOut0.node.type=='REROUTE')or(skOut1.node.type=='REROUTE') )and(self.prefs.vmReroutesCanInAnyType)
                    if tgl:
                        self.foundGoalSkOut1 = li
                        break
                if (self.foundGoalSkOut1)and(skOut0==self.foundGoalSkOut1.tg): #Проверка на самокопию.
                    self.foundGoalSkOut1 = None
                StencilUnCollapseNode(nd, self.foundGoalSkOut1)
            #Не смотря на то, что в фильтре нод нет нужды и и так прекрасно работает на первом попавшемся, всё равно нужно продолжать поиск, если первый сокет найден не был.
            #Потому что если первым(ближайшим) окажется нод с неудачным результатом поиска, цикл закончится и инструмент ничего не выберет, даже если рядом есть подходящий.
            if self.foundGoalSkOut0: #Особенно заметно с активным isCanReOut, без этого результат будет выбираться успешно/не-успешно в зависимости от положения курсора.
                break
    def modal(self, context, event):
        if StencilMouseNextAndReout(self, context, event, False, True):
            if result:=StencilModalEsc(self, context, event):
                return result
            if (self.foundGoalSkOut0)and(self.isCanFromOne or self.foundGoalSkOut1):
                mxData.sk0 = self.foundGoalSkOut0.tg
                mxData.sk1 = self.foundGoalSkOut1.tg if self.foundGoalSkOut1 else None
                #Поддержка виртуальных выключена; читается только из первого
                mxData.skType = mxData.sk0.type if mxData.sk0.bl_idname!='NodeSocketVirtual' else mxData.sk1.type
                mxData.isSpeedPie = self.prefs.vmPieType=='SPEED'
                mxData.isHideOptions = self.isHideOptions
                mxData.isPlaceImmediately = self.isPlaceImmediately
                mxData.pieScale = self.prefs.vmPieScale
                mxData.pieDisplaySocketTypeInfo = self.prefs.vmPieSocketDisplayType
                mxData.pieAlignment = self.prefs.vmPieAlignment
                di = dict_dictTupleMixerMain.get(context.space_data.tree_type, False)
                if not di: #Если место действия не в классических редакторах, то просто выйти. Ибо классические редакторы у всех одинаковые, а аддонских есть бесчисленное множество.
                    return {'CANCELLED'}
                di = di.get(mxData.skType, None)
                if di:
                    if length(di)==1: #Если выбор всего один, то пропустить его и сразу переходить к смешиванию.
                        DoMix(context, False, False, False, di[0]) #При моментальной активации пользователь мог и не отпускать модификаторы. Поэтому DoMix() получает не event, а вручную.
                    else: #Иначе предоставить выбор
                        bpy.ops.wm.call_menu_pie(name=MixerPie.bl_idname)
                else: #Иначе для типа сокета не определено. Например шейдер в геонодах.
                    def PopupMessage(self, context):
                        self.layout.label(text=txt_noMixingOptions, icon='RADIOBUT_OFF')
                    bpy.context.window_manager.popup_menu(PopupMessage, title="")
            return {'FINISHED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        if result:=UselessForCustomUndefTrees(context):
            return result
        if result:=StencilBeginToolInvoke(self, context, event):
            return result
        self.foundGoalSkOut0 = None
        self.foundGoalSkOut1 = None
        StencilToolWorkPrepare(self, context, CallbackDrawVoronoiMixer, True)
        return {'RUNNING_MODAL'}

SmartAddToRegAndAddToKmiDefs(VoronoiMixerTool, "LEFTMOUSE_ScA") #Миксер перенесён на левую, чтобы освободить нагрузку для VQMT.
dict_setKmiCats['g'].add(VoronoiMixerTool.bl_idname)

vmtSep = 'MixerItemsSeparator'
dict_dictTupleMixerMain = { #Порядок важен; самые частые(в этом списке) идут первее (кроме MixRGB).
        'ShaderNodeTree':     {'SHADER':     ('ShaderNodeMixShader','ShaderNodeAddShader'),
                               'VALUE':      ('ShaderNodeMixRGB',  'ShaderNodeMix',                      'ShaderNodeMath'),
                               'RGBA':       ('ShaderNodeMixRGB',  'ShaderNodeMix'),
                               'VECTOR':     ('ShaderNodeMixRGB',  'ShaderNodeMix',                                       'ShaderNodeVectorMath'),
                               'INT':        ('ShaderNodeMixRGB',  'ShaderNodeMix',                      'ShaderNodeMath')},
                               ##
        'GeometryNodeTree':   {'VALUE':      ('GeometryNodeSwitch','ShaderNodeMix','FunctionNodeCompare','ShaderNodeMath'),
                               'RGBA':       ('GeometryNodeSwitch','ShaderNodeMix','FunctionNodeCompare'),
                               'VECTOR':     ('GeometryNodeSwitch','ShaderNodeMix','FunctionNodeCompare',                 'ShaderNodeVectorMath'),
                               'STRING':     ('GeometryNodeSwitch',                'FunctionNodeCompare',                                        'GeometryNodeStringJoin'),
                               'INT':        ('GeometryNodeSwitch','ShaderNodeMix','FunctionNodeCompare','ShaderNodeMath'),
                               'BOOLEAN':    ('GeometryNodeSwitch','ShaderNodeMix','FunctionNodeCompare','ShaderNodeMath',                       'FunctionNodeBooleanMath'),
                               'ROTATION':   ('GeometryNodeSwitch','ShaderNodeMix'),
                               'OBJECT':     ('GeometryNodeSwitch',),
                               'MATERIAL':   ('GeometryNodeSwitch',),
                               'COLLECTION': ('GeometryNodeSwitch',),
                               'TEXTURE':    ('GeometryNodeSwitch',),
                               'IMAGE':      ('GeometryNodeSwitch',),
                               'GEOMETRY':   ('GeometryNodeSwitch','GeometryNodeJoinGeometry','GeometryNodeInstanceOnPoints','GeometryNodeCurveToMesh','GeometryNodeMeshBoolean','GeometryNodeGeometryToInstance')},
                               ##
        'CompositorNodeTree': {'VALUE':      ('CompositorNodeMath',     vmtSep,'CompositorNodeMixRGB','CompositorNodeSwitch','CompositorNodeSplitViewer','CompositorNodeSwitchView'),
                               'RGBA':       ('CompositorNodeAlphaOver',vmtSep,'CompositorNodeMixRGB','CompositorNodeSwitch','CompositorNodeSplitViewer','CompositorNodeSwitchView'),
                               'VECTOR':     (                          vmtSep,'CompositorNodeMixRGB','CompositorNodeSwitch','CompositorNodeSplitViewer','CompositorNodeSwitchView'),
                               'INT':        ('CompositorNodeMath',     vmtSep,'CompositorNodeMixRGB','CompositorNodeSwitch','CompositorNodeSplitViewer','CompositorNodeSwitchView')},
                               ##
        'TextureNodeTree':    {'VALUE':      ('TextureNodeMixRGB','TextureNodeTexture','TextureNodeMath'),
                               'RGBA':       ('TextureNodeMixRGB','TextureNodeTexture'),
                               'VECTOR':     ('TextureNodeMixRGB',                                        'TextureNodeDistance'),
                               'INT':        ('TextureNodeMixRGB','TextureNodeTexture','TextureNodeMath')}}
dict_tupleMixerNodesDefs = { #'-1' означает визуальную здесь метку, что их сокеты подключения высчитываются автоматически (см. |2|), а не указаны явно в этом списке
        #Отсортировано по количеству в "базе данных" выше.
        'GeometryNodeSwitch':             (-1, -1, "Switch"),
        'ShaderNodeMix':                  (-1, -1, "Mix"),
        'FunctionNodeCompare':            (-1, -1, "Compare"),
        'ShaderNodeMath':                 (0, 1, "Max Float"),
        'ShaderNodeMixRGB':               (1, 2, "Mix RGB"),
        'CompositorNodeMixRGB':           (1, 2, "Mix Col"),
        'CompositorNodeSwitch':           (0, 1, "Switch"),
        'CompositorNodeSplitViewer':      (0, 1, "Split Viewer"),
        'CompositorNodeSwitchView':       (0, 1, "Switch View"),
        'TextureNodeMixRGB':              (1, 2, "Mix Col"),
        'TextureNodeTexture':             (0, 1, "Texture"),
        'ShaderNodeVectorMath':           (0, 1, "Max Vector"),
        'CompositorNodeMath':             (0, 1, "Max Float"),
        'TextureNodeMath':                (0, 1, "Max Float"),
        'ShaderNodeMixShader':            (1, 2, "Mix Shader"),
        'ShaderNodeAddShader':            (0, 1, "Add Shader"),
        'GeometryNodeStringJoin':         (1, 1, "Join String"),
        'FunctionNodeBooleanMath':        (0, 1, "Or"),
        'CompositorNodeAlphaOver':        (1, 2, "Alpha Over"),
        'TextureNodeDistance':            (0, 1, "Distance"),
        'GeometryNodeJoinGeometry':       (0, 0, "Join"),
        'GeometryNodeInstanceOnPoints':   (0, 2, "Instance on Points"),
        'GeometryNodeCurveToMesh':        (0, 1, "Curve to Mesh"),
        'GeometryNodeMeshBoolean':        (0, 1, "Boolean"),
        'GeometryNodeGeometryToInstance': (0, 0, "To Instance")}
def DoMix(context, isS, isC, isA, txt_node):
    tree = context.space_data.edit_tree
    if not tree:
        return
    bpy.ops.node.add_node('INVOKE_DEFAULT', type=txt_node, use_transform=not mxData.isPlaceImmediately)
    aNd = tree.nodes.active
    aNd.width = 140
    txtFix = {'VALUE':'FLOAT'}.get(mxData.skType, mxData.skType)
    #Дважды switch case -- для комфортного кода и немножко экономии.
    match aNd.bl_idname:
        case 'ShaderNodeMath'|'ShaderNodeVectorMath'|'CompositorNodeMath'|'TextureNodeMath':
            aNd.operation = 'MAXIMUM'
        case 'FunctionNodeBooleanMath':
            aNd.operation = 'OR'
        case 'TextureNodeTexture':
            aNd.show_preview = False
        case 'GeometryNodeSwitch':
            aNd.input_type = txtFix
        case 'FunctionNodeCompare':
            aNd.data_type = {'BOOLEAN':'INT'}.get(txtFix, txtFix)
            aNd.operation = 'EQUAL'
        case 'ShaderNodeMix':
            aNd.data_type = {'INT':'FLOAT', 'BOOLEAN':'FLOAT'}.get(txtFix, txtFix)
    match aNd.bl_idname:
        case 'GeometryNodeSwitch'|'FunctionNodeCompare'|'ShaderNodeMix': #|2|.
            tgl = aNd.bl_idname!='FunctionNodeCompare'
            txtFix = mxData.skType
            match aNd.bl_idname:
                case 'FunctionNodeCompare': txtFix = {'BOOLEAN':'INT'}.get(txtFix, txtFix)
                case 'ShaderNodeMix':       txtFix = {'INT':'VALUE', 'BOOLEAN':'VALUE'}.get(txtFix, txtFix)
            #Для микса и переключателя искать с конца, потому что их сокеты для переключения имеют тип некоторых искомых. У нода сравнения всё наоборот.
            list_foundSk = [sk for sk in ( reversed(aNd.inputs) if tgl else aNd.inputs ) if sk.type==txtFix]
            NewLinkAndRemember(mxData.sk0, list_foundSk[tgl^isS]) #Из-за направления поиска, нужно выбирать их из списка так же с учётом направления.
            if mxData.sk1:
                NewLinkAndRemember(mxData.sk1, list_foundSk[(not tgl)^isS])
        case _:
            #Такая плотная суета ради мультиинпута -- для него нужно изменить порядок подключения.
            if (mxData.sk1)and(aNd.inputs[dict_tupleMixerNodesDefs[aNd.bl_idname][0]].is_multi_input): #`0` здесь в основном из-за того, что в dict_tupleMixerNodesDefs у "нодов-мультиинпутов" всё по нулям.
                NewLinkAndRemember( mxData.sk1, aNd.inputs[dict_tupleMixerNodesDefs[aNd.bl_idname][1^isS]] )
            DoLinkHH( mxData.sk0, aNd.inputs[dict_tupleMixerNodesDefs[aNd.bl_idname][0^isS]] ) #Это не NewLinkAndRemember(), чтобы визуальный второй мультиинпута был последним в rpData.
            if (mxData.sk1)and(not aNd.inputs[dict_tupleMixerNodesDefs[aNd.bl_idname][0]].is_multi_input):
                NewLinkAndRemember( mxData.sk1, aNd.inputs[dict_tupleMixerNodesDefs[aNd.bl_idname][1^isS]] )
    if mxData.isHideOptions:
        aNd.show_options = False
    #Далее так же, как и в vqmt. У него первично; здесь дублировано для интуитивного соответствия.
    if isA:
        for sk in aNd.inputs:
            NewLinkAndRemember(mxData.sk0, sk)
    if isC:
        for sk in aNd.inputs:
            sk.hide = True

class MixerMixer(VoronoiOp):
    bl_idname = 'node.voronoi_mixer_mixer'
    bl_label = "Mixer Mixer"
    txt: bpy.props.StringProperty()
    def invoke(self, context, event):
        DoMix(context, event.shift, event.ctrl, event.alt, self.txt)
        return {'FINISHED'}
class MixerPie(bpy.types.Menu):
    bl_idname = 'VL_MT_voronoi_mixer_pie'
    bl_label = "" #Текст здесь будет отображаться в центре пирога.
    def draw(self, context):
        pie = self.layout.menu_pie()
        def AddOp(where, txt):
            if mxData.pieAlignment==1:
                where = where.row()
            where.operator(MixerMixer.bl_idname, text=dict_tupleMixerNodesDefs[txt][2], translate=False).txt = txt
        dict_items = dict_dictTupleMixerMain[context.space_data.tree_type][mxData.skType]
        if mxData.isSpeedPie:
            for li in dict_items:
                if li!=vmtSep:
                    AddOp(pie, li)
        else:
            #Если при выполнении колонка окажется пустой, то в ней будет отображаться только пустая точка-коробка. Два списка ниже нужны, чтобы починить это.
            list_cols = [pie.row(), pie.row(), pie.row() if mxData.pieDisplaySocketTypeInfo>0 else None]
            list_done = [False, False, False]
            def PieCol(inx):
                if list_done[inx]:
                    return list_cols[inx]
                box = list_cols[inx].box()
                col = box.column(align=mxData.pieAlignment<2)
                col.ui_units_x = 6*((mxData.pieScale-1)/2+1)
                col.scale_y = mxData.pieScale
                list_cols[inx] = col
                list_done[inx] = True
                return col
            match context.space_data.tree_type:
                case 'ShaderNodeTree':
                    row2 = PieCol(0).row(align=mxData.pieAlignment==0)
                    row2.enabled = False
                    AddOp(row2, 'ShaderNodeMix')
                case 'GeometryNodeTree':
                    row1 = PieCol(0).row(align=mxData.pieAlignment==0)
                    row2 = PieCol(0).row(align=mxData.pieAlignment==0)
                    row3 = PieCol(0).row(align=mxData.pieAlignment==0)
                    row1.enabled = False
                    row2.enabled = False
                    row3.enabled = False
                    AddOp(row1, 'GeometryNodeSwitch')
                    AddOp(row2, 'ShaderNodeMix')
                    AddOp(row3, 'FunctionNodeCompare')
            sco = 0
            for li in dict_items:
                match li:
                    case 'GeometryNodeSwitch':  row1.enabled = True
                    case 'ShaderNodeMix':       row2.enabled = True
                    case 'FunctionNodeCompare': row3.enabled = True
                    case _:
                        if li==vmtSep:
                            if sco:
                                PieCol(1).separator()
                        else:
                            AddOp(PieCol(1), li)
                            sco += 1
            if mxData.pieDisplaySocketTypeInfo:
                box = pie.box()
                row = box.row(align=True)
                row.template_node_socket(color=GetSkCol(mxData.sk0))
                row.label(text=mxData.sk0.bl_label)

list_classes += [MixerMixer, MixerPie]

class QuickMathData:
    list_displayItems = []
    sk0 = None
    sk1 = None
    depth = 0
    qmSkType = ''
    qmTrueSkType = ''
    isHideOptions = False
    isPlaceImmediately = False
    isSpeedPie = False
    pieScale = 0
    pieDisplaySocketTypeInfo = 0
    pieAlignment = 0
    dict_lastOperation = {}
qmData = QuickMathData()

#Используется CallbackDraw от Миксера! Потому что одинаковы.

class VoronoiQuickMathTool(VoronoiToolDblSk):
    bl_idname = 'node.voronoi_quick_math'
    bl_label = "Voronoi Quick Math"
    quickOprFloat:  bpy.props.StringProperty(name="Float (quick)",  default="") #Они в начале, чтобы в kmi отображалось выровненным.
    quickOprVector: bpy.props.StringProperty(name="Vector (quick)", default="") #quick вторым, чтобы при нехватке места отображалось первое слово, от чего пришлось заключить в скобки.
    isCanFromOne:       bpy.props.BoolProperty(name="Can from one socket", default=True)
    isRepeatLastOperation: bpy.props.BoolProperty(name="Repeat last operation", default=False) #Что ж, квартет qqm теперь вынуждает их постоянно выравнивать.
    isHideOptions:      bpy.props.BoolProperty(name="Hide node options",   default=False)
    isPlaceImmediately: bpy.props.BoolProperty(name="Place immediately",   default=False)
    quickOprBool:   bpy.props.StringProperty(name="Bool (quick)",   default="")
    quickOprColor:  bpy.props.StringProperty(name="Color (quick)",  default="")
    justCallPie:           bpy.props.IntProperty(name="Just call pie", default=0, min=0, max=4)
    def NextAssignment(self, context, isBoth):
        if not context.space_data.edit_tree:
            return
        if isBoth:
            self.foundGoalSkOut0 = None
        self.foundGoalSkOut1 = None
        callPos = context.space_data.cursor_location
        isBothSucessSwitch = True
        sco = 0
        for li in GetNearestNodes(context.space_data.edit_tree.nodes, callPos):
            sco += 1
            nd = li.tg
            list_fgSksOut = GetNearestSockets(nd, callPos)[1]
            if not list_fgSksOut:
                continue
            #Этот инструмент триггерится только на выходы поля.
            if (isBoth)and(isBothSucessSwitch):
                isSucessOut = False
                for li in list_fgSksOut:
                    if not self.isRepeatLastOperation:
                        if not self.isQuickQuickMath:
                            if li.tg.type in set_skTypeFields:
                                self.foundGoalSkOut0 = li
                                isSucessOut = True
                                break
                        else: #Для isQuickQuickMath присасываться только к типам сокетов от явно указанных операций.
                            match li.tg.type:
                                case 'VALUE'|'INT':     isSucessOut = self.quickOprFloat
                                case 'VECTOR':          isSucessOut = self.quickOprVector
                                case 'BOOLEAN':         isSucessOut = self.quickOprBool
                                case 'RGBA'|'ROTATION': isSucessOut = self.quickOprColor
                            if isSucessOut:
                                self.foundGoalSkOut0 = li
                                break
                    else:
                        isSucessOut = qmData.dict_lastOperation.get(li.tg.type, '')
                        if isSucessOut:
                            self.foundGoalSkOut0 = li
                            break
                if not isSucessOut:
                    continue #Искать нод, у которого попадёт на сокет поля.
                    #Если так ничего и не найдёт, то мб isBothSucessSwitch стоит равным как в VMT; слишком дебри, моих навыков не хватает.
                nd.hide = False #После чего в любом случае развернуть его.
            isBothSucessSwitch = False #Для следующего `continue`, ибо если далее будет неудача с последующей активацией continue, то произойдёт перевыбор isBoth.
            #Для второго по условиям:
            skOut0 = self.foundGoalSkOut0.tg if self.foundGoalSkOut0 else None
            if skOut0:
                isSucessIn = False
                for li in list_fgSksOut:
                    if SkBetweenFieldsCheck(self, skOut0, li.tg):
                        self.foundGoalSkOut1 = li
                        isSucessIn = True
                        break
                if not isSucessIn:
                    continue
                if (self.foundGoalSkOut1)and(skOut0==self.foundGoalSkOut1.tg): #Проверка на самокопию.
                    self.foundGoalSkOut1 = None
                StencilUnCollapseNode(nd, self.foundGoalSkOut1) #Заметка: нод isBoth'а разворачивается здесь.
            break
    def modal(self, context, event):
        if StencilMouseNextAndReout(self, context, event, False, True):
            if result:=StencilModalEsc(self, context, event):
                return result
            if (self.foundGoalSkOut0)and(self.isCanFromOne or self.foundGoalSkOut1):
                qmData.sk0 = self.foundGoalSkOut0.tg
                qmData.sk1 = self.foundGoalSkOut1.tg if self.foundGoalSkOut1 else None
                qmData.isHideOptions = self.isHideOptions
                qmData.isPlaceImmediately = self.isPlaceImmediately
                qmData.qmSkType = qmData.sk0.type #Заметка: наличие только сокетов поля -- забота на уровень выше.
                qmData.qmTrueSkType = qmData.qmSkType #Эта информация нужна для "последней операции".
                match qmData.sk0.type:
                    case 'INT':      qmData.qmSkType = 'VALUE' #И только целочисленный обделён своим нодом математики. Может его добавят когда-нибудь?.
                    case 'ROTATION': qmData.qmSkType = 'RGBA' #Больше шансов, что для математика для кватерниона будет первее.
                    #case 'ROTATION': return {'FINISHED'} #Однако странно, почему с RGBA линки отмечаются не корректными, ведь оба Arr4... Зачем тогда цвету альфа?
                match context.space_data.tree_type:
                    case 'ShaderNodeTree':     qmData.qmSkType = {'BOOLEAN':'VALUE'}.get(qmData.qmSkType, qmData.qmSkType)
                    case 'GeometryNodeTree':   pass
                    case 'CompositorNodeTree': qmData.qmSkType = {'BOOLEAN':'VALUE', 'VECTOR':'RGBA'}.get(qmData.qmSkType, qmData.qmSkType)
                    case 'TextureNodeTree':    qmData.qmSkType = {'BOOLEAN':'VALUE', 'VECTOR':'RGBA'}.get(qmData.qmSkType, qmData.qmSkType)
                if self.isRepeatLastOperation:
                    return DoQuickMath(event, context.space_data.edit_tree, qmData.dict_lastOperation[qmData.qmTrueSkType], True)
                if self.isQuickQuickMath:
                    match qmData.qmSkType:
                        case 'VALUE':   txt_opr = self.quickOprFloat
                        case 'VECTOR':  txt_opr = self.quickOprVector
                        case 'BOOLEAN': txt_opr = self.quickOprBool
                        case 'RGBA':    txt_opr = self.quickOprColor
                    return DoQuickMath(event, context.space_data.edit_tree, txt_opr, True)
                qmData.depth = 0
                qmData.isSpeedPie = self.prefs.vqmPieType=='SPEED'
                qmData.pieScale = self.prefs.vqmPieScale
                qmData.pieDisplaySocketTypeInfo = self.prefs.vqmPieSocketDisplayType
                qmData.pieAlignment = self.prefs.vqmPieAlignment
                bpy.ops.node.voronoi_quick_math_main('INVOKE_DEFAULT')
                return {'FINISHED'}
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        if result:=UselessForCustomUndefTrees(context):
            return result
        if result:=StencilBeginToolInvoke(self, context, event):
            return result
        if self.justCallPie:
            match context.space_data.tree_type:
                case 'ShaderNodeTree': can = self.justCallPie in {1,2,4}
                case 'GeometryNodeTree': can = True
                case 'CompositorNodeTree'|'TextureNodeTree': can = self.justCallPie in {1,4}
            if not can:
                def PopupMessage(self, context): #todo3 сделать общую функцию.
                    self.layout.label(text="There is nothing")#, icon='INFO') #"Ничего нет".
                bpy.context.window_manager.popup_menu(PopupMessage, title="")
                return {'CANCELLED'}
            qmData.sk0 = None #Обнулять для полноты картины и для GetSkCol().
            qmData.sk1 = None
            qmData.isHideOptions = self.isHideOptions
            qmData.isPlaceImmediately = self.isPlaceImmediately
            qmData.qmSkType = ('VALUE','VECTOR','BOOLEAN','RGBA')[self.justCallPie-1]
            qmData.depth = 0
            qmData.isSpeedPie = self.prefs.vqmPieType=='SPEED'
            qmData.pieScale = self.prefs.vqmPieScale
            qmData.pieDisplaySocketTypeInfo = self.prefs.vqmPieSocketDisplayType
            qmData.pieAlignment = self.prefs.vqmPieAlignment
            bpy.ops.node.voronoi_quick_math_main('INVOKE_DEFAULT')
            return {'FINISHED'}
        self.foundGoalSkOut0 = None
        self.foundGoalSkOut1 = None
        self.isQuickQuickMath = not not( (self.quickOprFloat)or(self.quickOprVector)or(self.quickOprBool)or(self.quickOprColor) )
        StencilToolWorkPrepare(self, context, CallbackDrawVoronoiMixer, True)
        return {'RUNNING_MODAL'}

SmartAddToRegAndAddToKmiDefs(VoronoiQuickMathTool, "RIGHTMOUSE_ScA") #Осталось на правой, чтобы не охреневать от тройного клика левой при 'Speed Pie' типе пирога.
SmartAddToRegAndAddToKmiDefs(VoronoiQuickMathTool, "ACCENT_GRAVE_scA", {'isRepeatLastOperation':True})
#Список быстрых операций для быстрой математики ("x2 комбо"):
#Дилемма с логическим на "3", там может быть вычитание, как все на этой клавише, или отрицание, как логическое продолжение первых двух. Во втором случае булеан на 4 скорее всего придётся делать никаким.
SmartAddToRegAndAddToKmiDefs(VoronoiQuickMathTool, "1_scA", {'quickOprFloat':'ADD',      'quickOprVector':'ADD',      'quickOprBool':'OR',     'quickOprColor':'ADD'      })
SmartAddToRegAndAddToKmiDefs(VoronoiQuickMathTool, "2_scA", {'quickOprFloat':'SUBTRACT', 'quickOprVector':'SUBTRACT', 'quickOprBool':'NIMPLY', 'quickOprColor':'SUBTRACT' })
SmartAddToRegAndAddToKmiDefs(VoronoiQuickMathTool, "3_scA", {'quickOprFloat':'MULTIPLY', 'quickOprVector':'MULTIPLY', 'quickOprBool':'AND',    'quickOprColor':'MULTIPLY' })
SmartAddToRegAndAddToKmiDefs(VoronoiQuickMathTool, "4_scA", {'quickOprFloat':'DIVIDE',   'quickOprVector':'DIVIDE',   'quickOprBool':'NOT',    'quickOprColor':'DIVIDE'   })
#Хотел я реализовать это для QuickMathMain, но оказалось слишком лажа превращать технический оператор в пользовательский. Основная проблема -- qmData настроек пирога.
SmartAddToRegAndAddToKmiDefs(VoronoiQuickMathTool, "1_ScA", {'justCallPie':1}) #Неожиданно, но такой хоткей весьма приятный.
SmartAddToRegAndAddToKmiDefs(VoronoiQuickMathTool, "2_ScA", {'justCallPie':2}) # Из-за двух модификаторв приходится держать нажатым,
SmartAddToRegAndAddToKmiDefs(VoronoiQuickMathTool, "3_ScA", {'justCallPie':3}) # от чего приходится выбирать позицией курсора, а не кликом.
SmartAddToRegAndAddToKmiDefs(VoronoiQuickMathTool, "4_ScA", {'justCallPie':4}) # Я думал это будет неудобно, а оказалось даже приятно.
dict_setKmiCats['g'].add(VoronoiQuickMathTool.bl_idname)

#Быстрая математика.
#Заполучить нод с нужной операцией и автоматическим соединением в сокеты, благодаря мощностям VL'а.
#Неожиданно для меня оказалось, что пирог может рисовать обычный layout. От чего добавил дополнительный тип пирога "для контроля".
#А так же сам буду пользоваться им, потому что за то время, которое экономится при двойном пироге, отдохнуть как-то всё равно не получается.
#Важная эстетическая ценность двойного пирога -- визуальная неперегруженность вариантами. Вместо того, чтобы вываливать всё сразу, показываются только по 8 штук за раз.

#Заметка для самого меня: сохранять поддержку двойного пирога чёрт возьми, ибо эстетика. Но выпилить его с каждым разом хочется всё больше D:

#Было бы бездумно разбросать их как попало, поэтому я пытался соблюсти некоторую логическую последовательность. Например, расставляя пары по смыслу диаметрально противоположными.
#Пирог Блендера располагает в себе элементы следующим образом: лево, право, низ, верх, после чего классическое построчное заполнение.
#"Compatible..." -- чтобы у векторов и у математики одинаковые операции были на одинаковых местах (кроме тригонометрических).

#За исключением примитивов, где прослеживается супер очевидная логика (право -- плюс -- add, лево -- минус -- sub; всё как на числовой оси),
# лево и низ у меня более просты, чем обратная сторона.
#Например, length проще, чем distance. Всем же остальным не очевидным и не осе-ориентированным досталось как получится.
tuple_tupleQuickMathMapValue = (
        ("Advanced",              ('SQRT',       'POWER',        'EXPONENT',   'LOGARITHM',   'INVERSE_SQRT','PINGPONG'                      )),
        ("Compatible Primitives", ('SUBTRACT',   'ADD',          'DIVIDE'   ,  'MULTIPLY',    'ABSOLUTE',    'MULTIPLY_ADD'                  )),
        ("Rounding",              ('SMOOTH_MIN', 'SMOOTH_MAX',   'LESS_THAN',  'GREATER_THAN','SIGN',        'COMPARE',     'TRUNC',  'ROUND')),
        ("Compatible Vector",     ('MINIMUM',    'MAXIMUM',      'FLOOR',      'FRACT',        'CEIL',       'MODULO',      'SNAP',   'WRAP' )),
        ("", ()), #Важны дубликаты и порядок, поэтому не словарь а список.
        ("", ()),
        ("Other",                 ('COSH',       'RADIANS',      'DEGREES',    'SINH',        'TANH'                                         )),
        ("Trigonometric",         ('SINE',       'COSINE',       'TANGENT',    'ARCTANGENT',  'ARCSINE',     'ARCCOSINE',   'ARCTAN2'        )) )
tuple_tupleQuickMathMapVector = (
        ("Advanced",              ('SCALE',      'NORMALIZE',    'LENGTH',     'DISTANCE',    'SINE',        'COSINE',      'TANGENT'       )),
        ("Compatible Primitives", ('SUBTRACT',   'ADD',          'DIVIDE',     'MULTIPLY',    'ABSOLUTE',    'MULTIPLY_ADD'                 )),
        ("Rays",                  ('DOT_PRODUCT','CROSS_PRODUCT','PROJECT',    'FACEFORWARD', 'REFRACT',     'REFLECT'                      )),
        ("Compatible Vector",     ('MINIMUM',    'MAXIMUM',      'FLOOR',      'FRACTION',    'CEIL',        'MODULO',      'SNAP',   'WRAP')),
        ("", ()),
        ("", ()),
        ("", ()),
        ("", ()) )
tuple_tupleQuickMathMapBoolean = (
        ("High",  ('NOR','NAND','XNOR','XOR','IMPLY','NIMPLY')),
        ("Basic", ('OR', 'AND', 'NOT'                        )) )
tuple_tupleQuickModeMapColor = (
        #Для операции 'MIX' используйте VMT.
        ("Math", ('SUBTRACT','ADD',       'DIVIDE','MULTIPLY','DIFFERENCE','EXCLUSION'                    )), #'EXCLUSION' не влез в "Art"; и было бы не плохо узнать его предназначение.
        ("Art",  ('DARKEN',  'LIGHTEN','   DODGE', 'SCREEN',  'SOFT_LIGHT','LINEAR_LIGHT','BURN','OVERLAY')),
        ("Raw",  ('VALUE',   'SATURATION','HUE',   'COLOR'                                                )) ) #Хотел переназвать на "Overwrite", но передумал.
dict_quickMathMain = {
        'VALUE':   tuple_tupleQuickMathMapValue,
        'VECTOR':  tuple_tupleQuickMathMapVector,
        'BOOLEAN': tuple_tupleQuickMathMapBoolean,
        'RGBA':    tuple_tupleQuickModeMapColor}
#Ассоциация нода для типа редактора и сокета
dict_dictQmEditorNodes = {
        'VALUE':   {'ShaderNodeTree':     'ShaderNodeMath',
                    'GeometryNodeTree':   'ShaderNodeMath',
                    'CompositorNodeTree': 'CompositorNodeMath',
                    'TextureNodeTree':    'TextureNodeMath'},
        ##
        'VECTOR':  {'ShaderNodeTree':     'ShaderNodeVectorMath',
                    'GeometryNodeTree':   'ShaderNodeVectorMath'},
        ##
        'BOOLEAN': {'GeometryNodeTree':   'FunctionNodeBooleanMath'},
        ##
        'RGBA':    {'ShaderNodeTree':     'ShaderNodeMix',
                    'GeometryNodeTree':   'ShaderNodeMix',
                    'CompositorNodeTree': 'CompositorNodeMixRGB',
                    'TextureNodeTree':    'TextureNodeMixRGB'} }
#Значения по умолчанию для сокетов в зависимости от операции
dict_dictDefaultValueOperation = {
        'VALUE': {'MULTIPLY':(1.0, 1.0, 1.0),
                  'DIVIDE':  (1.0, 1.0, 1.0),
                  'POWER':   (2.0, 1/3, 0.0),
                  'SQRT':    (2.0, 2.0, 2.0),
                  'ARCTAN2': (math.pi, math.pi, math.pi)},
        'VECTOR': {'MULTIPLY':     ( (1,1,1), (1,1,1), (1,1,1), 1.0 ),
                   'DIVIDE':       ( (1,1,1), (1,1,1), (1,1,1), 1.0 ),
                   'CROSS_PRODUCT':( (0,0,1), (0,0,1), (0,0,1), 1.0 ),
                   'SCALE':        ( (0,0,0), (0,0,0), (0,0,0), math.pi )},
        'BOOLEAN': {'AND': (True, True),
                    'NOR': (True, True),
                    'XOR': (False, True),
                    'XNOR': (False, True),
                    'IMPLY': (True, False),
                    'NIMPLY': (True, False)},
        'RGBA': {'ADD':       ( (0,0,0,1), (0,0,0,1) ),
                 'SUBTRACT':  ( (0,0,0,1), (0,0,0,1) ),
                 'MULTIPLY':  ( (1,1,1,1), (1,1,1,1) ),
                 'DIVIDE':    ( (1,1,1,1), (1,1,1,1) ),
                 'DIFFERENCE':( (0,0,0,1), (1,1,1,1) ),
                 'EXCLUSION': ( (0,0,0,1), (1,1,1,1) ),
                 'VALUE':     ( (1,1,1,1), (1,1,1,1) ),
                 'SATURATION':( (1,1,1,1), (0,0,1,1) ),
                 'HUE':       ( (1,1,1,1), (0,1,0,1) ),
                 'COLOR':     ( (1,1,1,1), (1,0,0,1) ) } }
dict_defaultDefault = {
        #Заметка: основано на типе нода, а не на типе сокета. Повезло, что они одинаковые.
        'VALUE': (0.0, 0.0, 0.0),
        'VECTOR': ((0,0,0), (0,0,0), (0,0,0), 0.0),
        'BOOLEAN': (False, False),
        'RGBA': ( (.25,.25,.25,1), (.5,.5,.5,1) ) } #Можно было оставить без изменений, но всё равно обнуляю. Ради чего был создан VQMT?
def DoQuickMath(event, tree, opr, isQqo=False):
    txt = dict_dictQmEditorNodes[qmData.qmSkType].get(tree.bl_idname, "")
    if not txt: #Если нет в списке, то этот нод не существует (по задумке списка) в этом типе редактора => "смешивать" нечем, поэтому выходим.
        return {'CANCELLED'}
    #Ядро быстрой математики, добавить нод и создать линки:
    bpy.ops.node.add_node('INVOKE_DEFAULT', type=txt, use_transform=not qmData.isPlaceImmediately)
    aNd = tree.nodes.active
    if qmData.qmSkType!='RGBA': #Ох уж этот цвет.
        aNd.operation = opr
    else:
        if aNd.bl_idname=='ShaderNodeMix':
            aNd.data_type = 'RGBA'
        aNd.blend_type = opr
        aNd.inputs[0].default_value = 1.0
        aNd.inputs[0].hide = opr in {'ADD','SUBTRACT','DIVIDE','MULTIPLY','DIFFERENCE','EXCLUSION','VALUE','SATURATION','HUE','COLOR'}
    #Теперь существует justCallPie, а значит пришло время скрывать значение первого сокета (но нужда в этом только для вектора).
    if qmData.qmSkType=='VECTOR':
        aNd.inputs[0].hide_value = True
    #Идея с event.shift гениальна. Изначально ради одиночного линка во второй сокет, но благодаря визуальному поиску ниже, может и менять местами два линка.
    bl4ofs = 2*isBlender4*(tree.bl_idname in {'ShaderNodeTree','GeometryNodeTree'})
    skInx = aNd.inputs[0] if qmData.qmSkType!='RGBA' else aNd.inputs[-2-bl4ofs] #"Inx", потому что пародия на int "index", но потом понял, что можно сразу в сокет для линковки далее.
    if event.shift:
        for sk in aNd.inputs:
            if (sk!=skInx)and(sk.enabled)and(not sk.links):
                if sk.type==skInx.type:
                    skInx = sk
                    break
    if qmData.sk0:
        NewLinkAndRemember(qmData.sk0, skInx)
        if qmData.sk1:
            #Второй ищется "визуально"; сделано ради операции 'SCALE'.
            for sk in aNd.inputs: #Ищется сверху вниз. Потому что ещё и 'MulAdd'.
                if (sk.enabled)and(not sk.links):
                    #Ох уж этот скейл; единственный с двумя сокетами разных типов.
                    if (sk.type==skInx.type)or(opr=='SCALE'): #Искать одинаковый по типу. Актуально для RGBA Mix.
                        NewLinkAndRemember(qmData.sk1, sk)
                        break #Нужно соединить только в первый попавшийся, иначе будет соединено во все (например у 'MulAdd').
        elif (not isQqo)and(event.alt): #Если alt, то соединить первый во все.
            for sk in aNd.inputs:
                if sk.type==skInx.type:
                    NewLinkAndRemember(qmData.sk0, sk)
    #Установить значение по умолчанию для второго сокета (большинство нули). Нужно для красоты; и вообще это математика.
    #Заметка: нод вектора уже создаётся по нулям, так что для него обнулять без нужды.
    tuple_default = dict_defaultDefault[qmData.qmSkType]
    if qmData.qmSkType!='RGBA':
        for cyc, sk in enumerate(aNd.inputs):
            #Нет проверок на видимость и линки, пихать значение насильно. Потому что я так захотел.
            sk.default_value = dict_dictDefaultValueOperation[qmData.qmSkType].get(opr, tuple_default)[cyc]
    else: #Оптимизация для экономии в dict_dictDefaultValueOperation.
        tuple_col = dict_dictDefaultValueOperation[qmData.qmSkType].get(opr, tuple_default)
        aNd.inputs[-2-bl4ofs].default_value = tuple_col[0]
        aNd.inputs[-1-bl4ofs].default_value = tuple_col[1]
    #Скрыть все сокеты по запросу. На покерфейсе, ибо залинкованные сокеты всё равно не скроются; и даже без проверки 'sk.enabled'.
    if event.ctrl:
        for sk in aNd.inputs:
            sk.hide = True
    if qmData.isHideOptions:
        aNd.show_options = False
    return {'FINISHED'}
class QuickMathMain(VoronoiOp):
    bl_idname = 'node.voronoi_quick_math_main'
    bl_label = "Quick Math"
    operation: bpy.props.StringProperty()
    def modal(self, context, event):
        #Раньше нужно было отчищать мост вручную, потому что он оставался равным последней записи. Сейчас уже не нужно.
        return {'FINISHED'}
    def invoke(self, context, event):
        #Заметка: использование здесь ForseSetSelfNonePropToDefault() уже не работает задуманным образом для непрямого вызова этого оператора.
        tree = context.space_data.edit_tree
        if not tree:
            return {'CANCELLED'}
        match qmData.depth:
            case 0:
                if qmData.isSpeedPie:
                    qmData.list_displayItems = [ti[0] for ti in dict_quickMathMain[qmData.qmSkType]]
                else:
                    qmData.depth += 1
            case 1:
                if qmData.isSpeedPie:
                    qmData.list_displayItems = [ti[1] for ti in dict_quickMathMain[qmData.qmSkType] if ti[0]==self.operation][0] #Заметка: вычленяется кортеж из генератора.
            case 2:
                #Запоминать нужно только и очевидно только здесь. В Tool только qqm и rlo. Для qqm не запоминается для удобства, и следованию логики rlo.
                qmData.dict_lastOperation[qmData.qmTrueSkType] = self.operation
                return DoQuickMath(event, tree, self.operation, False)
        qmData.depth += 1
        bpy.ops.wm.call_menu_pie(name=QuickMathPie.bl_idname)
        return {'RUNNING_MODAL'}
class QuickMathPie(bpy.types.Menu):
    bl_idname = 'VL_MT_voronoi_quick_math_pie'
    bl_label = "" #Текст здесь будет отображаться в центре пирога.
    def draw(self, context):
        def AddOp(where, txt, ico='NONE'):
            if not qmData.isSpeedPie:
                where = where.row(align=True)
                if (qmData.pieDisplaySocketTypeInfo==2)and(colCurSk):
                    col = where.column()
                    if qmData.pieScale>1.25:
                        row = col.column()
                        row.label()
                        row.scale_y = (qmData.pieScale-1.2)/2
                    row = col.column()
                    row.template_node_socket(color=colCurSk)
                rowOp = where.row(align=qmData.pieAlignment==0)
                #Из-за 'pieDisplaySocketTypeInfo==2' масштаб устанавливается здесь для каждого оператора, а не в GetPieCol().
                rowOp.ui_units_x = 5.5*((qmData.pieScale-1)/2+1)
                rowOp.scale_y = qmData.pieScale
                where = rowOp
            #Автоматический перевод выключен, ибо оригинальные операции у нода математики тоже не переводятся.
            where.operator(QuickMathMain.bl_idname, text=txt.capitalize() if qmData.depth else txt, icon=ico, translate=False).operation = txt
        pie = self.layout.menu_pie()
        colCurSk = GetSkCol(qmData.sk0) if qmData.sk0 else None #Скорее всего есть ненулевая эстетика в том, что для justCallPie цвет сокета не отображается (по крайней мере для psdt=1).
        if qmData.isSpeedPie:
            for li in qmData.list_displayItems:
                if not li: #Для пустых записей в базе данных для быстрого пирога.
                    row = pie.row() #Ибо благодаря этому отображается никаким и занимает место.
                    continue
                AddOp(pie, li)
        else:
            def GetPieCol(where):
                col = where.column(align=qmData.pieAlignment<2)
                return col
            colLeft = GetPieCol(pie)
            colRight = GetPieCol(pie)
            colCenter = GetPieCol(pie)
            if qmData.pieDisplaySocketTypeInfo==1:
                colLabel = pie.column()
                box = colLabel.box()
                row = box.row(align=True)
                if colCurSk:
                    row.template_node_socket(color=colCurSk)
                match qmData.qmSkType:
                    case 'VALUE':   txt = "Float Quick Math"
                    case 'VECTOR':  txt = "Vector Quick Math"
                    case 'BOOLEAN': txt = "Boolean Quick Math"
                    case 'RGBA':    txt = "Color Quick Mode"
                row.label(text=txt)
                row.alignment = 'CENTER'
            def DrawForVecVal(isVec):
                AddOp(colRight,'ADD',     'ADD')
                AddOp(colRight,'SUBTRACT','REMOVE')
                AddOp(colRight,'MULTIPLY','SORTBYEXT')
                AddOp(colRight,'DIVIDE',  'ITALIC') #ITALIC  FIXED_SIZE  DECORATE_LINKED
                colRight.separator()
                AddOp(colRight, 'MULTIPLY_ADD')
                AddOp(colRight, 'ABSOLUTE')
                colRight.separator()
                for li in ('SINE','COSINE','TANGENT'):
                    AddOp(colCenter, li, 'FORCE_HARMONIC')
                if not isVec:
                    for li in ('POWER','SQRT','EXPONENT','LOGARITHM','INVERSE_SQRT','PINGPONG'):
                        AddOp(colRight, li)
                    colRight.separator()
                    AddOp(colRight, 'RADIANS')
                    AddOp(colRight, 'DEGREES')
                    AddOp(colLeft, 'FRACT', 'IPO_LINEAR')
                    for li in ('ARCTANGENT','ARCSINE','ARCCOSINE'):
                        AddOp(colCenter, li, 'RNA')
                    for li in ('ARCTAN2','SINH','COSH','TANH'):
                        AddOp(colCenter, li)
                else:
                    for li in ('SCALE','NORMALIZE','LENGTH','DISTANCE'):
                        AddOp(colRight, li)
                    colRight.separator()
                    AddOp(colLeft, 'FRACTION', 'IPO_LINEAR')
                AddOp(colLeft,'FLOOR','IPO_CONSTANT')
                AddOp(colLeft,'CEIL')
                AddOp(colLeft,'MAXIMUM','NONE') #SORT_DESC  TRIA_UP_BAR
                AddOp(colLeft,'MINIMUM','NONE') #SORT_ASC  TRIA_DOWN_BAR
                for li in ('MODULO', 'SNAP', 'WRAP'):
                    AddOp(colLeft, li)
                colLeft.separator()
                if not isVec:
                    for li in ('GREATER_THAN','LESS_THAN','TRUNC','SIGN','SMOOTH_MAX','SMOOTH_MIN','ROUND','COMPARE'):
                        AddOp(colLeft, li)
                else:
                    AddOp(colLeft,'DOT_PRODUCT',  'LAYER_ACTIVE')
                    AddOp(colLeft,'CROSS_PRODUCT','ORIENTATION_LOCAL') #OUTLINER_DATA_EMPTY  ORIENTATION_LOCAL  EMPTY_ARROWS
                    AddOp(colLeft,'PROJECT',      'CURVE_PATH') #SNAP_OFF  SNAP_ON  MOD_SIMPLIFY  CURVE_PATH
                    AddOp(colLeft,'FACEFORWARD',  'ORIENTATION_NORMAL')
                    AddOp(colLeft,'REFRACT',      'NODE_MATERIAL') #MOD_OFFSET  NODE_MATERIAL
                    AddOp(colLeft,'REFLECT',      'INDIRECT_ONLY_OFF') #INDIRECT_ONLY_OFF  INDIRECT_ONLY_ON
            def DrawForBool():
                AddOp(colRight,'AND')
                AddOp(colRight,'OR')
                AddOp(colRight,'NOT')
                AddOp(colLeft,'NAND')
                AddOp(colLeft,'NOR')
                AddOp(colLeft,'XOR')
                AddOp(colLeft,'XNOR')
                AddOp(colCenter,'IMPLY')
                AddOp(colCenter,'NIMPLY')
            def DrawForCol():
                for li in ('LIGHTEN','DARKEN','SCREEN','DODGE','LINEAR_LIGHT','SOFT_LIGHT','OVERLAY','BURN'):
                    AddOp(colRight, li)
                for li in ('ADD','SUBTRACT','MULTIPLY','DIVIDE','DIFFERENCE','EXCLUSION'):
                    AddOp(colLeft, li)
                for li in ('VALUE','SATURATION','HUE','COLOR'):
                    AddOp(colCenter, li)
            match qmData.qmSkType:
                case 'VALUE'|'VECTOR': DrawForVecVal(qmData.qmSkType=='VECTOR')
                case 'BOOLEAN': DrawForBool()
                case 'RGBA': DrawForCol()

list_classes += [QuickMathMain, QuickMathPie]

def CallbackDrawVoronoiSwapper(self, context):
    if StencilStartDrawCallback(self, context):
        return
    cusorPos = context.space_data.cursor_location
    if self.foundGoalSkIo0:
        DrawToolOftenStencil( self, cusorPos, [self.foundGoalSkIo0], isLineToCursor=True, isDrawText=False )
        tgl = not not self.foundGoalSkIo1
        DrawMixerSkText(self, cusorPos, self.foundGoalSkIo0, -0.5+0.75*tgl, int(tgl))
        if tgl:
            DrawToolOftenStencil( self, cusorPos, [self.foundGoalSkIo1], isLineToCursor=True, isDrawText=False )
            DrawMixerSkText(self, cusorPos, self.foundGoalSkIo1, -1.25, -1)
    elif self.prefs.dsIsDrawPoint:
        DrawWidePoint(self, cusorPos)
class VoronoiSwapperTool(VoronoiToolDblSk):
    bl_idname = 'node.voronoi_swaper'
    bl_label = "Voronoi Swapper"
    isAddMode:      bpy.props.BoolProperty(name="Add mode",               default=False)
    isIgnoreLinked: bpy.props.BoolProperty(name="Ignore linked",          default=False)
    isCanAnyType:   bpy.props.BoolProperty(name="Can swap with any type", default=False)
    def NextAssignment(self, context, isBoth):
        if not context.space_data.edit_tree:
            return
        if isBoth:
            self.foundGoalSkIo0 = None
        self.foundGoalSkIo1 = None
        callPos = context.space_data.cursor_location
        isBothSucessSwitch = True
        for li in GetNearestNodes(context.space_data.edit_tree.nodes, callPos):
            nd = li.tg
            if StencilUnCollapseNode(nd, isBoth):
                #|4| Чтобы начать отсчёт снизу, туда нужно переместиться на высоту нода. А нод-то свёрнут! Поэтому его нужно развернуть перед вычислением сокетов с перерисовкой.
                bpy.ops.wm.redraw_timer(type='DRAW_WIN', iterations=0)
            list_fgSksIn, list_fgSksOut = GetNearestSockets(nd, callPos)
            #За основу были взяты критерии от Миксера.
            if (isBoth)and(isBothSucessSwitch):
                fgSkOut, fgSkIn = None, None
                for li in list_fgSksOut:
                    if li.tg.bl_idname!='NodeSocketVirtual':
                        if (not self.isIgnoreLinked)or(li.tg.is_linked):
                            fgSkOut = li
                            break
                for li in list_fgSksIn:
                    if li.tg.bl_idname!='NodeSocketVirtual':
                        if (not self.isIgnoreLinked)or(li.tg.is_linked):
                            fgSkIn = li
                            break
                #Разрешить возможность "добавлять" и для входов тоже, но только для мультиинпутов, ибо очевидное
                if (self.isAddMode)and(fgSkIn):
                    #Проверка по типу, но не по 'is_multi_input', чтобы из обычного в мультиинпут можно было добавлять.
                    if (fgSkIn.tg.bl_idname not in ('NodeSocketGeometry','NodeSocketString')):#or(not fgSkIn.tg.is_multi_input): #Без второго условия больше возможностей.
                        fgSkIn = None
                self.foundGoalSkIo0 = MinFromFgs(fgSkOut, fgSkIn)
                if (self.isIgnoreLinked)and(self.foundGoalSkIo0)and(not self.foundGoalSkIo0.tg.is_linked):
                    self.foundGoalSkIo0 = None
                    #Заметка: важно продолжать искать сокет с линком, ибо ради повышения удобства было создано isIgnoreLinked.
            isBothSucessSwitch = not self.foundGoalSkIo0
            #Здесь вокруг аккумулировалось много странных проверок с None и т.п. -- результат соединения вместе многих типа высокоуровневых функций, что я понаизобретал.
            skOut0 = self.foundGoalSkIo0.tg if self.foundGoalSkIo0 else None
            if skOut0:
                for li in list_fgSksOut if skOut0.is_output else list_fgSksIn:
                    if li.tg.bl_idname=='NodeSocketVirtual':
                        continue
                    if (self.isCanAnyType)or(skOut0.type==li.tg.type)or( SkBetweenFieldsCheck(self, skOut0, li.tg) ):
                        #Последнее условие нужно для ломания цикла самокопией, чтобы при активации VST isIgnoreLinked не находил сразу два сокета.
                        if (not(self.isIgnoreLinked and li.tg.is_linked))or(li.tg==skOut0):
                            self.foundGoalSkIo1 = li
                    if self.foundGoalSkIo1: #В случае успеха прекращать поиск.
                        break
                if (self.foundGoalSkIo1)and(skOut0==self.foundGoalSkIo1.tg): #Проверка на самокопию.
                    self.foundGoalSkIo1 = None
                    break #Ломать для isCanAnyType, когда isBoth==False и сокет оказался самокопией; чтобы не находил сразу два нода.
                if not self.isCanAnyType:
                    if not(self.foundGoalSkIo1 or isBoth): #Если нет результата, продолжаем искать.
                        continue
                StencilUnCollapseNode(nd, self.foundGoalSkIo1)
            break
    def modal(self, context, event):
        if StencilMouseNextAndReout(self, context, event, False, True):
            if result:=StencilModalEsc(self, context, event):
                return result
            if (self.foundGoalSkIo0)and(self.foundGoalSkIo1):
                skIo0 = self.foundGoalSkIo0.tg
                skIo1 = self.foundGoalSkIo1.tg
                tree = context.space_data.edit_tree
                if self.isAddMode:
                    #Просто добавить линки с первого сокета на второй. Aka объединение, добавление.
                    if skIo0.is_output:
                        for lk in skIo0.links:
                            if lk.to_node!=skIo1.node: # T 1  Чтобы линк от нода не создался сам в себя. Проверять нужно у всех и таковые не обрабатывать.
                                tree.links.new(skIo1, lk.to_socket)
                                if lk.to_socket.is_multi_input: #Без этого lk всё равно указывает на "добавленный" линк, от чего удаляется. Поэтому явная проверка для мультиинпутов.
                                    tree.links.remove(lk)
                    else: #Добавлено ради мультиинпутов.
                        for lk in skIo0.links:
                            if lk.from_node!=skIo1.node: # F 1  ^
                                tree.links.new(lk.from_socket, skIo1)
                                tree.links.remove(lk)
                else:
                    #Поменять местами все соединения у первого и у второго сокета:
                    list_memSks = []
                    if skIo0.is_output: #Проверка одинаковости is_output -- забота для NextAssignment().
                        for lk in skIo0.links:
                            if lk.to_node!=skIo1.node: # T 1  Чтобы линк от нода не создался сам в себя. Проверять нужно у всех и таковые не обрабатывать.
                                list_memSks.append(lk.to_socket)
                                tree.links.remove(lk)
                        for lk in skIo1.links:
                            if lk.to_node!=skIo0.node: # T 0  ^
                                tree.links.new(skIo0, lk.to_socket)
                                if lk.to_socket.is_multi_input: #Для мультиинпутов удалить.
                                    tree.links.remove(lk)
                        for li in list_memSks:
                            tree.links.new(skIo1, li)
                    else:
                        for lk in skIo0.links:
                            if lk.from_node!=skIo1.node: # F 1  ^
                                list_memSks.append(lk.from_socket)
                                tree.links.remove(lk)
                        for lk in skIo1.links:
                            if lk.from_node!=skIo0.node: # F 0  ^
                                tree.links.new(lk.from_socket, skIo0)
                                tree.links.remove(lk)
                        for li in list_memSks:
                            tree.links.new(li, skIo1)
                #VST VRT же без нужды, да?
                return {'FINISHED'}
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        if result:=StencilBeginToolInvoke(self, context, event):
            return result
        self.foundGoalSkIo0 = None
        self.foundGoalSkIo1 = None
        StencilToolWorkPrepare(self, context, CallbackDrawVoronoiSwapper, True)
        return {'RUNNING_MODAL'}

SmartAddToRegAndAddToKmiDefs(VoronoiSwapperTool, "S_Sca")
SmartAddToRegAndAddToKmiDefs(VoronoiSwapperTool, "S_scA", {'isAddMode':True })
SmartAddToRegAndAddToKmiDefs(VoronoiSwapperTool, "S_sCA", {'isAddMode':False, 'isIgnoreLinked':True })
dict_setKmiCats['o'].add(VoronoiSwapperTool.bl_idname)

#Нужен только для наведения порядка и эстетики в дереве.
#Для тех, кого (например меня) напрягают "торчащие без дела" пустые сокеты выхода, или нулевые (чьё значение 0.0, чёрный, и т.п.) незадействованные сокеты входа.
def CallbackDrawVoronoiHider(self, context):
    if StencilStartDrawCallback(self, context):
        return
    cusorPos = context.space_data.cursor_location
    if self.isHideSocket:
        if self.foundGoalTg:
            DrawToolOftenStencil( self, cusorPos, [self.foundGoalTg], isLineToCursor=True, textSideFlip=True )
        elif self.prefs.dsIsDrawPoint:
            DrawWidePoint(self, cusorPos)
    else:
        DrawNodeStencilFull(self, cusorPos, self.foundGoalTg, self.prefs.vhDrawNodeNameLabel, self.prefs.vhLabelDispalySide)
class VoronoiHiderTool(VoronoiToolSkNd):
    bl_idname = 'node.voronoi_hider'
    bl_label = "Voronoi Hider"
    isHideSocket: bpy.props.IntProperty(name="Hide mode", min=0, max=2)
    isTriggerOnCollapsedNodes: bpy.props.BoolProperty(name="Trigger on collapsed nodes", default=True)
    def NextAssignment(self, context, *naArgs):
        if not context.space_data.edit_tree:
            return
        self.foundGoalTg = None
        callPos = context.space_data.cursor_location
        for li in GetNearestNodes(context.space_data.edit_tree.nodes, callPos):
            nd = li.tg
            if (not self.isTriggerOnCollapsedNodes)and(nd.hide):
                continue
            #Для этого инструмента рероуты пропускаются, по очевидным причинам.
            if nd.type=='REROUTE':
                continue
            self.foundGoalTg = li
            if self.isHideSocket:
                #Для режима сокетов обработка свёрнутости так же как у всех.
                list_fgSksIn, list_fgSksOut = GetNearestSockets(nd, callPos)
                def GetNotLinked(list_sks): #Выдать первого, кто не имеет линков.
                    for li in list_sks:
                        if not li.tg.links: #Выключенный сокет всё равно учитывается.
                            return li
                fgSkIn = GetNotLinked(list_fgSksIn)
                fgSkOut = GetNotLinked(list_fgSksOut)
                if self.isHideSocket==1:
                    self.foundGoalTg = MinFromFgs(fgSkOut, fgSkIn)
                else:
                    self.foundGoalTg = fgSkIn
                if StencilUnCollapseNode(nd, self.foundGoalTg):
                    StencilReNext(self, context) #Для режима сокетов тоже нужно перерисовывать, ибо нод у присосавшегося сокета может быть свёрнут.
            else:
                #Для режима нод нет разницы, раскрывать все подряд под курсором, или нет.
                if self.prefs.vhIsToggleNodesOnDrag:
                    if self.firstResult is None:
                        #Если активация для нода ничего не изменила, то для остальных хочется иметь сокрытие, а не раскрытие. Но текущая концепция не позволяет,
                        # информации об этом тупо нет. Поэтому реализовал это точечно вовне (здесь), а не модификацией самой реализации.
                        LGetVisSide = lambda io: [sk for sk in io if sk.enabled and not sk.hide]
                        list_visibleSks = [LGetVisSide(nd.inputs),LGetVisSide(nd.outputs)]
                        self.firstResult = HideFromNode(self, nd, True)
                        HideFromNode(self, nd, self.firstResult, True) #Заметка: изменить для нода (для проверки ниже), но не трогать 'self.firstResult'.
                        if list_visibleSks==[LGetVisSide(nd.inputs),LGetVisSide(nd.outputs)]:
                            self.firstResult = True
                    HideFromNode(self, nd, self.firstResult, True)
                    #См. в вики, почему isReDrawAfterChange опция была удалена.
                    #todo1 Единственное возможное решение, так это сделать изменение нода после отрисовки одного кадра.
                    # Т.е. присосаться к новому ноду на один кадр, а потом уже обработать его сразу с поиском нового нода и рисовки к нему (как для примера в вики).
            break
    def modal(self, context, event):
        if StencilMouseNextAndReout(self, context, event):
            if result:=StencilModalEsc(self, context, event):
                return result
            if self.foundGoalTg:
                match self.isHideSocket:
                    case 0: #Обработка нода.
                        if not self.prefs.vhIsToggleNodesOnDrag:
                            #Во время сокрытия сокета нужно иметь информацию обо всех, поэтому выполняется дважды. В первый заход собирается, во второй выполняется.
                            HideFromNode(self, self.foundGoalTg.tg, HideFromNode(self, self.foundGoalTg.tg, True), True)
                    case 1: #Сокрытие сокета.
                        self.foundGoalTg.tg.hide = True
                    case 2: #Переключение видимости значения сокета.
                        self.foundGoalTg.tg.hide_value = not self.foundGoalTg.tg.hide_value
            return {'FINISHED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        if result:=StencilBeginToolInvoke(self, context, event):
            return result
        self.foundGoalTg = []
        self.firstResult = None #Получить действие "свернуть" или "развернуть" у первого нода, а потом транслировать его на все остальные попавшиеся.
        StencilToolWorkPrepare(self, context, CallbackDrawVoronoiHider)
        return {'RUNNING_MODAL'}

SmartAddToRegAndAddToKmiDefs(VoronoiHiderTool, "E_Sca", {'isHideSocket':1})
SmartAddToRegAndAddToKmiDefs(VoronoiHiderTool, "E_scA", {'isHideSocket':2})
SmartAddToRegAndAddToKmiDefs(VoronoiHiderTool, "E_sCa", {'isHideSocket':0})
dict_setKmiCats['o'].add(VoronoiHiderTool.bl_idname)

def HideFromNode(self, ndTarget, lastResult, isCanDo=False): #Изначально лично моя утилита, была создана ещё до VL.
    set_equestrianHideVirtual = {'GROUP_INPUT','SIMULATION_INPUT','SIMULATION_OUTPUT','REPEAT_INPUT','REPEAT_OUTPUT'}
    scoGeoSks = 0 #Для CheckSkZeroDefaultValue().
    def CheckSkZeroDefaultValue(sk): #Shader и Virtual всегда True, Geometry от настроек аддона.
        match sk.type: #Отсортированы в порядке убывания сложности.
            case 'GEOMETRY':
                match self.prefs.vhNeverHideGeometry: #Задумывалось и для out тоже, но как-то леновато, а ещё `GeometryNodeBoundBox`, так что...
                    case 'FALSE': return True
                    case 'TRUE': return False
                    case 'ONLY_FIRST':
                        nonlocal scoGeoSks
                        scoGeoSks += 1
                        return scoGeoSks!=1
            case 'VALUE':
                if (GetSkLabelName(sk) in {'Alpha', 'Factor'})and(sk.default_value==1): #Для некоторых флоат сокетов тоже было бы неплохо иметь точечную проверку.
                    return True #todo1 изобрести как-то список настраиваемых точечных сокрытий.
                return sk.default_value==0
            case 'VECTOR':
                if (GetSkLabelName(sk)=='Scale')and(sk.default_value[0]==1)and(sk.default_value[1]==1)and(sk.default_value[2]==1):
                    return True #Меня переодически напрягал 'GeometryNodeTransform', и в один прекрасной момент накопилось..
                return (sk.default_value[0]==0)and(sk.default_value[1]==0)and(sk.default_value[2]==0) #Заметка: `sk.default_value==(0,0,0)` не прокатит.
            case 'BOOLEAN':
                if not sk.hide_value: #Лень паять, всё обрабатывается в прямом виде.
                    match self.prefs.vhHideBoolSocket: #Заметка: `.self` всего один, но зато каждый NextAssignment() инструмента, причём по несколько за раз. Так что маршрут self'ов имел смысл.
                        case 'ALWAYS': return True
                        case 'NEVER': return False
                        case 'IF_TRUE': return sk.default_value
                        case 'IF_FALSE': return not sk.default_value
                else:
                    match self.prefs.vhHideHiddenBoolSocket:
                        case 'ALWAYS': return True
                        case 'NEVER': return False
                        case 'IF_TRUE': return sk.default_value
                        case 'IF_FALSE': return not sk.default_value
            case 'RGBA':
                return (sk.default_value[0]==0)and(sk.default_value[1]==0)and(sk.default_value[2]==0) #4-й компонент игнорируются, может быть любым.
            case 'INT':
                return sk.default_value==0
            case 'STRING'|'OBJECT'|'MATERIAL'|'COLLECTION'|'TEXTURE'|'IMAGE': #Заметка: STRING не такой же, как и остальные, но имеет одинаковую обработку.
                return not sk.default_value
            case _:
                return True
    if lastResult: #Результат предыдущего анализа, есть ли сокеты чьё состояние изменилось бы. Нужно для 'isCanDo'.
        def CheckAndDoForIo(ioputs, LMainCheck):
            success = False
            for sk in ioputs:
                if (sk.enabled)and(not sk.hide)and(not sk.links)and(LMainCheck(sk)): #Ядро сокрытия находится здесь, в первых двух проверках.
                    success |= not sk.hide #Здесь success означает будет ли оно скрыто.
                    if isCanDo:
                        sk.hide = True
            return success
        #Если виртуальные были созданы вручную, то не скрывать их. Потому что. Но если входов групп больше одного, то всё равно скрывать.
        #Изначальный смысл LVirtual -- "LCheckOver" -- проверка "над", точечные дополнительные условия. Но в ней скопились только для виртуальных, поэтому переназвал.
        isMoreNgInputs = False if ndTarget.type!='GROUP_INPUT' else ( length([True for nd in ndTarget.id_data.nodes if nd.type=='GROUP_INPUT'])>1 )
        LVirtual = lambda sk: not( (sk.bl_idname=='NodeSocketVirtual')and #Смысл этой Labmda -- точечное не-сокрытие для тех, которые виртуальные,
                                   (sk.node.type in {'GROUP_INPUT','GROUP_OUTPUT'})and # у io-всадников,
                                   (sk!=(sk.node.outputs if sk.is_output else sk.node.inputs)[-1])and # и не последние (то ради чего),
                                   (not isMoreNgInputs) ) # и GROUP_INPUT в дереве всего один.
        #Ядро в трёх строчках ниже:
        success = CheckAndDoForIo(ndTarget.inputs, lambda sk: CheckSkZeroDefaultValue(sk)and(LVirtual(sk)) ) #Для входов мейнстримная проверка их значений, и дополнительно виртуальные.
        if [True for sk in ndTarget.outputs if (sk.enabled)and(sk.links)]: #Если хотя бы один сокет подсоединён вовне
            success |= CheckAndDoForIo(ndTarget.outputs, lambda sk: LVirtual(sk) ) #Для выводов актуально только проверка виртуальных, если их нодом оказался всадник.
        else:
            #Всё равно переключать последний виртуальный, даже если нет соединений вовне.
            if ndTarget.type in set_equestrianHideVirtual: #Заметка: 'GROUP_OUTPUT' бесполезен, у него всё прячется по значению.
                if ndTarget.outputs: #Вместо for, чтобы читать из последнего.
                    sk = ndTarget.outputs[-1]
                    if sk.bl_idname=='NodeSocketVirtual':
                        success |= not sk.hide #Так же, как и в CheckAndDoForIo().
                        if isCanDo:
                            sk.hide = True
        return success #Урожай от двух CheckAndDoForIo() изнутри.
    elif isCanDo: #Иначе раскрыть всё.
        success = False
        for ioputs in {ndTarget.inputs, ndTarget.outputs}:
            for sk in ioputs:
                success |= sk.hide #Здесь success означает будет ли оно раскрыто.
                sk.hide = (sk.bl_idname=='NodeSocketVirtual')and(not self.prefs.vhIsUnhideVirtual)
        return success

#"Массовый линкер" -- как линкер, только много за раз (ваш кэп).
#См. вики на гитхабе, что бы посмотреть 4 примера использования массового линкера. Дайте мне знать, если обнаружите ещё одно необычное применение этому инструменту.

def CallbackDrawVoronoiMassLinker(self, context):
    #Здесь нарушается местная концепция чтения-записи, и CallbackDraw ищет и записывает найденные сокеты вместо того, чтобы просто читать и рисовать. Полагаю, так инструмент реализовывать проще.
    try:
        if StencilStartDrawCallback(self, context):
            return
        cusorPos = context.space_data.cursor_location
        if not self.ndGoalOut:
            DrawDoubleNone(self, context)
        elif (self.ndGoalOut)and(not self.ndGoalIn):
            list_fgSksOut = GetNearestSockets(self.ndGoalOut, cusorPos)[1]
            if not list_fgSksOut:
                DrawDoubleNone(self, context)
            for li in list_fgSksOut: #Не известно, к кому это будет подсоединено и к кому получится => рисовать от всех сокетов.
                DrawToolOftenStencil( self, cusorPos, [li], isLineToCursor=self.prefs.dsIsAlwaysLine, isDrawText=False ) #Всем к курсору!
        else:
            self.list_equalFgSks = [] #Отчищать каждый раз.
            list_fgSksOut = GetNearestSockets(self.ndGoalOut, cusorPos)[1]
            list_fgSksIn =  GetNearestSockets(self.ndGoalIn,  cusorPos)[0]
            for liSko in list_fgSksOut:
                for liSki in list_fgSksIn:
                    #Т.к. "массовый" -- критерии приходится автоматизировать и сделать их едиными для всех.
                    if CompareSkLabelName(liSko.tg, liSki.tg): #Соединяться только с одинаковыми по именам сокетами.
                        tgl = False
                        if self.isIgnoreExistingLinks: #Если соединяться без разбору, то исключить уже имеющиеся "желанные" связи. Нужно только для эстетики.
                            for lk in liSki.tg.links:
                                #Проверка is_linked нужна, чтобы можно было включить выключенные линки, перезаменив их.
                                if (lk.from_socket.is_linked)and(lk.from_socket==liSko.tg):
                                    tgl = True
                            tgl = not tgl
                        else: #Иначе не трогать уже соединённых.
                            tgl = not liSki.tg.links
                        if tgl:
                            self.list_equalFgSks.append( (liSko,liSki) )
            if not self.list_equalFgSks:
                DrawWidePoint(self, cusorPos)
            for li in self.list_equalFgSks:
                #Т.к. поиск по именам, рисоваться здесь и подсоединяться ниже, возможно из двух (и больше) сокетов в один и тот же одновременно. Типа "конфликт" одинаковых имён.
                DrawToolOftenStencil( self, cusorPos, [li[0],li[1]], isDrawText=False )
    except Exception as ex:
        pass; print("VL CallbackDrawVoronoiMassLinker() --", ex)
class VoronoiMassLinkerTool(VoronoiTool): #"Малыш котопёс", не ноды, не сокеты.
    bl_idname = 'node.voronoi_mass_linker'
    bl_label = "Voronoi MassLinker" #Единственный, у кого нет пробела. Потому что слишком котопёсный))00)0
    # А если серьёзно, то он действительно самый странный. Пародирует VLT с его dsIsAlwaysLine. SocketArea стакаются, если из нескольких в одного. Пишет в функции рисования...
    # А ещё именно он есть/будет на превью аддона, ибо обладает самой большой степенью визуальности из всех инструментов (причем без верхнего предела).
    isIgnoreExistingLinks: bpy.props.BoolProperty(name="Ignore existing links", default=False)
    def NextAssignment(self, context, isBoth):
        if not context.space_data.edit_tree:
            return
        callPos = context.space_data.cursor_location
        for li in GetNearestNodes(context.space_data.edit_tree.nodes, callPos):
            nd = li.tg
            StencilUnCollapseNode(nd, isBoth)
            #Помимо свёрнутых так же игнорируются и рероуты, потому что у них инпуты всегда одни и с одинаковыми названиями.
            if nd.type=='REROUTE':
                continue
            self.ndGoalIn = nd
            if isBoth:
                self.ndGoalOut = nd #Здесь нод-вывод устанавливается один раз.
            if self.ndGoalOut==self.ndGoalIn: #Проверка на самокопию.
                self.ndGoalIn = None #Здесь нод-вход обнуляется каждый раз в случае неудачи.
            #Заметка: первое нахождение ndGoalIn, list_equalFgSks == [].
            if StencilUnCollapseNode(nd, self.ndGoalIn):
                StencilReNext(self, context, False)
            break
    def modal(self, context, event):
        #Заметка: ndGoalIn обнулится через самокопию если isCanReOut.
        if StencilMouseNextAndReout(self, context, event, False, True):
            if result:=StencilModalEsc(self, context, event):
                return result
            if (self.ndGoalOut)and(self.ndGoalIn):
                tree = context.space_data.edit_tree
                #for li in self.list_equalFgSks: tree.links.new(li[0].tg, li[1].tg) #Соединить всех!
                #Если выходы нода и входы другого нода имеют в сумме 4 одинаковых сокета по названию, то происходит неожидаемое от инструмента поведение.
                #Поэтому соединяется только один линк на входной сокет (мультиинпуты не в счёт).
                set_alreadyDone = set()
                list_skipToEndEq = []
                list_skipToEndSk = []
                for li in self.list_equalFgSks:
                    sko = li[0].tg
                    ski = li[1].tg
                    if ski in set_alreadyDone:
                        continue
                    if sko in list_skipToEndSk: #Заметка: достаточно и линейного чтения, но пока оставлю так, чтоб наверняка.
                        list_skipToEndEq.append(li)
                        continue
                    tree.links.new(sko, ski) #Заметка: наверное лучше оставить безопасное "сырое" соединение, учитывая массовость соединения и неограниченность количества.
                    RememberLastSockets(sko, ski) #Заметка: эта и далее -- "последнее всегда последнее", эффективно-ниже проверками уже не опуститься; ну или по крайней мере на моём уровне знаний.
                    if not ski.is_multi_input: #Мультиинпуты бездонны!
                        set_alreadyDone.add(ski)
                    list_skipToEndSk.append(sko)
                #Далее обрабатываются пропущенные на предыдущем цикле.
                for li in list_skipToEndEq:
                    sko = li[0].tg
                    ski = li[1].tg
                    if ski in set_alreadyDone:
                        continue
                    set_alreadyDone.add(ski)
                    tree.links.new(sko, ski)
                    RememberLastSockets(sko, ski)
                return {'FINISHED'}
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        if result:=StencilBeginToolInvoke(self, context, event):
            return result
        self.ndGoalOut = None
        self.ndGoalIn = None
        self.list_equalFgSks = [] #Однажды необычным странным образом, modal() не смог найти этот атрибут в себе. Поэтому продублировал сюда.
        self.isDrawDoubleNone = True
        StencilToolWorkPrepare(self, context, CallbackDrawVoronoiMassLinker, True)
        return {'RUNNING_MODAL'}

SmartAddToRegAndAddToKmiDefs(VoronoiMassLinkerTool, "LEFTMOUSE_SCA")
SmartAddToRegAndAddToKmiDefs(VoronoiMassLinkerTool, "RIGHTMOUSE_SCA", {'isIgnoreExistingLinks':True})
dict_setKmiCats['o'].add(VoronoiMassLinkerTool.bl_idname)

class EnumSelectorData:
    list_enumProps = [] #Для пайки, и проверка перед вызовом, есть ли вообще что.
    nd = None
    boxScale = 1.0 #Если забыть установить, то хотя бы коробка не сколлапсируется в ноль.
    isDarkStyle = False
    isDisplayLabels = False
    isPieChoice = False
esData = EnumSelectorData()

def GetListOfNdEnums(nd): #Так же использует VQDT.
    return [li for li in nd.rna_type.properties if not(li.is_readonly or li.is_registered)and(li.type=='ENUM')] #todo3 вспомнить, зачем нужен is_registered.

def CallbackDrawVoronoiEnumSelector(self, context):
    if StencilStartDrawCallback(self, context):
        return
    cusorPos = context.space_data.cursor_location
    if colNode:=DrawNodeStencilFull(self, cusorPos, self.foundGoalNd, self.prefs.vesDrawNodeNameLabel, self.prefs.vesLabelDispalySide, not self.prefs.vesIsDrawEnumNames):
        sco = -0.5
        col = colNode if self.prefs.dsIsColoredText else GetUniformColVec(self)
        for li in GetListOfNdEnums(self.foundGoalNd.tg):
            DrawText( self, cusorPos, (self.prefs.dsDistFromCursor, sco), TranslateIface(li.name), col)
            sco -= 1.5
def CallbackDrawVoronoiEnumSelectorNode(self, context): #Тут вся тусовка про... о нет.
    if StencilStartDrawCallback(self, context):
        return
    nd = self.foundGoalNd.tg
    colNd = PowerArr4ToVec(self.prefs.dsNodeColor, 1/2.2) #ToNodeCol и NodeCol -- это разное; второй опции нет, поэтому читать с первой.
    col = Vector(colNd.x, colNd.y, colNd.z, self.prefs.dsSocketAreaAlpha) #Vector не обязателен.
    loc = RecrGetNodeFinalLoc(nd)
    hh = nd.dimensions[1]/2-10 if nd.hide else 0 #Всё равно криво рисуется. Ну и хрен с ними.
    #Вычленёнка-алерт, DrawWidePoint().
    loc0 = VecWorldToRegScale(loc, self)
    loc1 = Vector(loc.x+6*1000, loc.y)
    sz = (VecWorldToRegScale(loc1, self)[0]-loc0[0])/1000
    #Вычленёнка-алерт, DrawSocketArea().
    pos1 = VecWorldToRegScale( Vector(loc.x, loc.y+1+hh), self ) #'+1' потому что не стыкуется ровно и наслаивается тонкой полоской. Ниже тоже.
    pos2 = VecWorldToRegScale( Vector(loc.x+nd.dimensions[0]+1, loc.y-nd.dimensions[1]+hh), self ) #Офигеть, 'nd.width' и 'nd.dimensions[0]' для свёрнутого нода -- оказывается разное.
    pos3 = Vector(pos1.x, pos2.y)
    pos4 = Vector(pos2.x, pos1.y)
    DrawRectangle(self, pos1+Vector(-sz, sz), pos3+Vector(0, -sz), col)
    DrawRectangle(self, pos4+Vector(sz, sz), pos2+Vector(0, -sz), col)
    DrawRectangle(self, pos1+Vector(0, sz), pos4, col)
    DrawRectangle(self, pos3+Vector(0, -sz), pos2, col)
class VoronoiEnumSelectorTool(VoronoiToolNd):
    bl_idname = 'node.voronoi_enum_selector'
    bl_label = "Voronoi Enum Selector"
    isToggleOptions: bpy.props.BoolProperty(name="Toggle node options mode", default=False)
    isPieChoice:     bpy.props.BoolProperty(name="Pie choice",               default=False)
    isSelectNode:    bpy.props.BoolProperty(name="Select target node",       default=True)
    def NextAssignment(self, context, *naArgs):
        if not context.space_data.edit_tree:
            return
        self.foundGoalNd = None
        callPos = context.space_data.cursor_location
        for li in GetNearestNodes(context.space_data.edit_tree.nodes, callPos, skipPoorNodes=False):
            nd = li.tg
            if nd.type=='REROUTE': #Для этого инструмента рероуты пропускаются, по очевидным причинам.
                continue
            if nd.bl_idname in set_equestrianPortalBlids: #Игнорировать всех всадников.
                continue
            if nd.hide: #У свёрнутых нод результат переключения не увидеть, поэтому игнорировать.
                continue
            if self.isToggleOptions:
                self.foundGoalNd = li
                #Так же, как и в VHT:
                if self.prefs.vesIsToggleNodesOnDrag:
                    if self.firstResult is None:
                        self.firstResult = ToggleOptionsFromNode(nd, True)
                    ToggleOptionsFromNode(nd, self.firstResult, True)
                break
            else:
                #Почему бы не игнорировать ноды без енум свойств?.
                if GetListOfNdEnums(nd):
                    self.foundGoalNd = li
                    break
    def DoActivation(self): #Для моментальной активации, сразу из invoke().
        if self.foundGoalNd:
            esData.list_enumProps = GetListOfNdEnums(self.foundGoalNd.tg)
            #Если ничего нет, то вызов коробки всё равно обрабатывается, словно она есть, и от чего повторный вызов инструмента не работает без движения курсора.
            if esData.list_enumProps: #Поэтому если пусто, то ничего не делаем.
                esData.nd = self.foundGoalNd.tg
                esData.boxScale = self.prefs.vesBoxScale
                esData.isDarkStyle = self.prefs.vesDarkStyle
                esData.isDisplayLabels = self.prefs.vesDisplayLabels
                esData.isPieChoice = self.isPieChoice
                if self.isSelectNode:
                    NdSelectAndActive(esData.nd)
                if self.isPieChoice:
                    bpy.ops.wm.call_menu_pie(name=EnumSelectorBox.bl_idname)
                else:
                    bpy.ops.node.voronoi_enum_selector_box('INVOKE_DEFAULT')
                return True #Для modal(), чтобы вернуть успех.
    def modal(self, context, event):
        if StencilMouseNextAndReout(self, context, event):
            if result:=StencilModalEsc(self, context, event):
                return result
            if self.isToggleOptions:
                if not self.prefs.vesIsToggleNodesOnDrag: #И снова, так же как и в VHT.
                    ToggleOptionsFromNode(self.foundGoalNd.tg, ToggleOptionsFromNode(self.foundGoalNd.tg, True), True)
                return {'FINISHED'}
            else:
                if (not self.prefs.vesIsInstantActivation)and(VoronoiEnumSelectorTool.DoActivation(self)):
                    return {'FINISHED'}
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        if result:=StencilBeginToolInvoke(self, context, event):
            return result
        self.foundGoalNd = None
        if (self.prefs.vesIsInstantActivation)and(not self.isToggleOptions):
            #Заметка: коробка может полностью закрыть нод вместе с линией к нему.
            VoronoiEnumSelectorTool.NextAssignment(self, context)
            VoronoiEnumSelectorTool.DoActivation(self)
            #Вычленёнка-алерт, StencilToolWorkPrepare().
            self.uiScale = UiScale()
            self.whereActivated = context.space_data
            self.handleNode = bpy.types.SpaceNodeEditor.draw_handler_add(CallbackDrawVoronoiEnumSelectorNode, (self,context), 'WINDOW', 'POST_PIXEL')
            #Гениально! Оно работает. Спасибо Blender'у, что не перерисовывает каждый раз, а только по запросу.
            #Но если isSelectNode, то рамка не остаётся. Ну.. и так сойдёт.
            bpy.ops.wm.redraw_timer(type='DRAW_WIN', iterations=0)
            bpy.types.SpaceNodeEditor.draw_handler_remove(self.handleNode, 'WINDOW')
            return {'FINISHED'} #Рисуется, но не позволяет использовать пирог при отжатии. Поэтому не нужно активировать modal() далее. Так же см. vesIsInstantActivation в modal().
        self.firstResult = None #В идеале тоже перед выше, но не обязательно, см. топологию isToggleOptions.
        StencilToolWorkPrepare(self, context, CallbackDrawVoronoiEnumSelector)
        return {'RUNNING_MODAL'}

#Изначально хотел 'V_Sca', но слишком далеко тянуться пальцем до 'V'. И вообще, учитывая причину создания этого инструмента, нужно минимизировать сложность вызова.
SmartAddToRegAndAddToKmiDefs(VoronoiEnumSelectorTool, "F_sca", {'isPieChoice':True     })
SmartAddToRegAndAddToKmiDefs(VoronoiEnumSelectorTool, "F_Sca", {                       })
SmartAddToRegAndAddToKmiDefs(VoronoiEnumSelectorTool, "F_scA", {'isToggleOptions':True })
dict_setKmiCats['o'].add(VoronoiEnumSelectorTool.bl_idname)

def DrawEnumSelectorBox(where, lyDomain=None):
    colMaster = where.column()
    colDomain = lyDomain.column() if lyDomain else None
    nd = esData.nd
    #Нод математики имеет высокоуровневое разбиение на категории для .prop(), но как показать их вручную простым перечислением я не знаю. И вообще, VQMT.
    #Игнорировать их не стал, пусть обрабатываются как есть. И с ними даже очень удобно выбирать операцию векторной математики (обычная не влезает).
    sco = 0
    #Домен всегда первым. Например, StoreNamedAttribute и FieldAtIndex имеют одинаковые енумы, но в разном порядке; интересно почему?.
    for li in sorted(esData.list_enumProps, key=lambda a:a.identifier!='domain'):
        if (sco)and(colWhere!=colDomain):
            colProp.separator()
        colWhere = (colDomain if (lyDomain)and(li.identifier=='domain') else colMaster)
        colProp = colWhere.column(align=True)
        if esData.isDisplayLabels:
            rowLabel = colProp.row(align=True)
            rowLabel.alignment = 'CENTER'
            rowLabel.label(text=li.name)
            #rowLabel.active = not esData.isPieChoice #Для пирога рамка прозрачная, от чего текст может сливаться с яркими нодами на фоне. Так что выключено.
            rowLabel.active = not(esData.isDarkStyle and esData.isPieChoice) #Но для тёмного пирога всё-таки отобразить их тёмными.
        elif sco:
            colProp.separator()
        colEnum = colProp.column(align=True)
        colEnum.scale_y = esData.boxScale
        if esData.isDarkStyle:
            colEnum.prop_tabs_enum(nd, li.identifier)
        else:
            colEnum.prop(nd, li.identifier, expand=True)
        sco += 1
    if not sco: #Для отладки.
        colMaster.label(text="`list_enums` is empty") #Во всю ширину не влезает.
    #В самой первой задумке я неправильно назвал этот инструмент -- "Prop Selector". Нужно придумать как отличить общие свойства нода от тех, которые рисуются у него в опциях.
    #Повезло, что у каждого нода енумов нет разных...
    #for li in [li for li in nd.rna_type.properties if not(li.is_readonly or li.is_registered)and(li.type!='ENUM')]: colMaster.prop(nd, li.identifier)
class OpEnumSelectorBox(VoronoiOp):
    bl_idname = 'node.voronoi_enum_selector_box'
    bl_label = "Enum Selector"
    def execute(self, context): #Для draw() ниже, иначе не отобразится.
        pass
    def draw(self, context):
        DrawEnumSelectorBox(self.layout)
    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=int(128*esData.boxScale))
class EnumSelectorBox(bpy.types.Menu):
    bl_idname = 'VL_MT_voronoi_enum_selector_box'
    bl_label = "Enum Selector"
    def draw(self, context):
        pie = self.layout.menu_pie()
        def GetCol(where, tgl=True):
            col = (where.box() if tgl else where) . column()
            col.ui_units_x = 7*((esData.boxScale-1)/2+1)
            return col
        colDom = GetCol(pie, [True for li in esData.list_enumProps if li.identifier=='domain'])
        colAll = GetCol(pie, [True for li in esData.list_enumProps if li.identifier!='domain'])
        DrawEnumSelectorBox(colAll, colDom)

list_classes += [OpEnumSelectorBox, EnumSelectorBox]

def ToggleOptionsFromNode(nd, lastResult, isCanDo=False): #Копия логики с VHT HideFromNode()'a.
    if lastResult:
        success = nd.show_options
        if isCanDo:
            nd.show_options = False
        return success
    elif isCanDo:
        success = not nd.show_options
        nd.show_options = True
        return success

#См. в начале файла: RepeatingData, RememberLastSockets() и NewLinkAndRemember().

def CallbackDrawVoronoiRepeating(self, context):
    if StencilStartDrawCallback(self, context):
        return
    cusorPos = context.space_data.cursor_location
    if self.isAutoRepeatMode:
        DrawNodeStencilFull(self, cusorPos, self.foundGoalTg, 'NONE', 0) #Здесь нет vrDrawNodeNameLabel. Может быть когда-нибудь добавлю.
    else:
        if self.foundGoalTg:
            DrawToolOftenStencil( self, cusorPos, [self.foundGoalTg] )
        else:
            DrawWidePoint(self, cusorPos)
class VoronoiRepeatingTool(VoronoiToolSkNd): #Вынесено в отдельный инструмент, чтобы не осквернять святая святых спагетти-кодом (изначально был только для VLT).
    bl_idname = 'node.voronoi_repeating'
    bl_label = "Voronoi Repeating"
    isAutoRepeatMode: bpy.props.BoolProperty(name="Is auto repeat mode", default=False)
    isFromOut:        bpy.props.BoolProperty(name="From out",            default=False)
    def NextAssignment(self, context, *naArgs):
        if not context.space_data.edit_tree:
            return
        lSkO = rpData.lastSk1
        if (not lSkO)or(lSkO.id_data!=context.space_data.edit_tree): #Перенесено в начало, чтобы не делать бесполезные вычисления.
            return
        self.foundGoalTg = None
        callPos = context.space_data.cursor_location
        for li in GetNearestNodes(context.space_data.edit_tree.nodes, callPos):
            nd = li.tg
            if nd==lSkO.node: #Исключить само-нод.
                break# continue
            if self.isAutoRepeatMode:
                lSkI = rpData.lastSk2
                if (self.isFromOut)or(lSkI):
                    if nd.inputs:
                        self.foundGoalTg = li
                    for sk in nd.inputs:
                        if CompareSkLabelName(sk, lSkO if self.isFromOut else lSkI):
                            if (sk.enabled)and(not sk.hide):
                                context.space_data.edit_tree.links.new(lSkO, sk) #Заметка: не высокоуровневый; зачем isAutoRepeatMode'у интерфейсы?.
            else:
                list_fgSksIn, list_fgSksOut = GetNearestSockets(nd, callPos)
                if rpData.lastSk1:
                    for li in list_fgSksIn:
                        can = True
                        for lk in li.tg.links:
                            if lk.from_socket==lSkO:
                                can = False
                        if can:
                            self.foundGoalTg = li
                            break
                if StencilUnCollapseNode(nd, self.foundGoalTg):
                    StencilReNext(self, context)
            break
    def modal(self, context, event):
        if StencilMouseNextAndReout(self, context, event):
            if result:=StencilModalEsc(self, context, event):
                return result
            if self.foundGoalTg:
                if not self.isAutoRepeatMode:
                    #Здесь нет нужды проверять на одинаковость дерева сокетов, проверка на это уже есть в NextAssignment().
                    #Так же нет нужды проверять существование lastSk1, см. его топологию в NextAssignment().
                    # if (rpData.lastSk1)and(rpData.lastSk1.id_data!=self.foundGoalTg.tg.id_data): return {'CANCELLED'}
                    #Нет нужды проверять существование дерева, потому что если присосавшийся сокет тут существует, то уже где-то.
                    DoLinkHH(rpData.lastSk1, self.foundGoalTg.tg)
                    RememberLastSockets(rpData.lastSk1, self.foundGoalTg.tg) #Потому что. И вообще.. "саморекурсия"?.
            return {'FINISHED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        if result:=StencilBeginToolInvoke(self, context, event):
            return result
        self.foundGoalTg = None
        #Проверить актуальность сокетов:
        tree = rpData.tree
        if not(tree is None):
            try: #Узнать, существует ли дерево.
                getattr(tree, 'rna_type') #hasattr() всё равно выдаёт ошибку.
            except:
                rpData.lastSk1 = None
                rpData.lastSk2 = None
            try:
                #Оказывается, Ctrl Z делает ссылку на tree `ReferenceError: StructRNA of type ShaderNodeTree has been removed`.
                #Пока у меня нет идей, как сохранить гарантированную "долгоиграющую" ссылку. Лепить rpData.lastNd1name в свойства каждого дерева не очень хочется.
                #Поэтому обработка через try, если неудача -- забыть всё текущее.
                nd = tree.nodes.get(rpData.lastNd1name)
                if (not nd)or(nd.as_pointer()!=rpData.lastNd1Id):
                    rpData.lastSk1 = None
                nd = tree.nodes.get(rpData.lastNd2name)
                if (not nd)or(nd.as_pointer()!=rpData.lastNd2Id):
                    rpData.lastSk2 = None
                #Можно было бы хранить все по именам, но тогда в разных деревьях могут оказаться одинаковые ноды и сокеты, благодаря чему будет не ожидаемое поведение от инструмента.
            except:
                rpData.tree = None
                #Остальные у rpData не удаляются, потому что топология rpData.tree перекрывает.
        ##
        StencilToolWorkPrepare(self, context, CallbackDrawVoronoiRepeating)
        return {'RUNNING_MODAL'}

SmartAddToRegAndAddToKmiDefs(VoronoiRepeatingTool, "V_sca")
SmartAddToRegAndAddToKmiDefs(VoronoiRepeatingTool, "V_Sca", {'isAutoRepeatMode':True })
SmartAddToRegAndAddToKmiDefs(VoronoiRepeatingTool, "V_scA", {'isAutoRepeatMode':True, 'isFromOut':True })
dict_setKmiCats['o'].add(VoronoiRepeatingTool.bl_idname)

dict_dictQuickDimensionsMain = {
        'ShaderNodeTree':    {'VECTOR':   ('ShaderNodeSeparateXYZ',),
                              'RGBA':     ('ShaderNodeSeparateColor',),
                              'VALUE':    ('ShaderNodeCombineXYZ','ShaderNodeCombineColor'),
                              'INT':      ('ShaderNodeCombineXYZ',)},
        'GeometryNodeTree':  {'VECTOR':   ('ShaderNodeSeparateXYZ',),
                              'RGBA':     ('FunctionNodeSeparateColor',),
                              'VALUE':    ('ShaderNodeCombineXYZ','FunctionNodeCombineColor','FunctionNodeQuaternionToRotation'),
                              'INT':      ('ShaderNodeCombineXYZ',),
                              'BOOLEAN':  ('ShaderNodeCombineXYZ',),
                              'ROTATION': ('FunctionNodeRotationToQuaternion',),
                              'GEOMETRY': ('GeometryNodeSeparateComponents',)}, #Зато одинаковый по смыслу. Воспринимать как мини-рофл.
        'CompositorNodeTree':{'VECTOR':   ('CompositorNodeSeparateXYZ',),
                              'RGBA':     ('CompositorNodeSeparateColor',),
                              'VALUE':    ('CompositorNodeCombineXYZ','CompositorNodeCombineColor'),
                              'INT':      ('CompositorNodeCombineXYZ',)},
        'TextureNodeTree':   {'VECTOR':   ('TextureNodeSeparateColor',),
                              'RGBA':     ('TextureNodeSeparateColor',),
                              'VALUE':    ('TextureNodeCombineColor',''), #Нет обработок отсутствия второго, поэтому пусто; см. |5|.
                              'INT':      ('TextureNodeCombineColor',)}}

def CallbackDrawVoronoiQuickDimensions(self, context):
    if StencilStartDrawCallback(self, context):
        return
    cusorPos = context.space_data.cursor_location
    if self.foundGoalSkOut0:
        #От VST. #todo2 CallbackDraw'ы тоже нужно стандартизировать и зашаблонить, причём более актуально.
        DrawToolOftenStencil( self, cusorPos, [self.foundGoalSkOut0], isLineToCursor=True, isDrawText=False )
        tgl = not not self.foundGoalSkOut1
        DrawMixerSkText(self, cusorPos, self.foundGoalSkOut0, -0.5+0.75*tgl, int(tgl))
        if tgl:
            DrawToolOftenStencil( self, cusorPos, [self.foundGoalSkOut1], isLineToCursor=True, isDrawText=False )
            DrawMixerSkText(self, cusorPos, self.foundGoalSkOut1, -1.25, -1)
    elif self.prefs.dsIsDrawPoint:
        DrawWidePoint(self, cusorPos)
class VoronoiQuickDimensionsTool(VoronoiToolSk):
    bl_idname = 'node.voronoi_quick_dimensions'
    bl_label = "Voronoi Quick Dimensions"
    isPlaceImmediately: bpy.props.BoolProperty(name="Place immediately", default=False)
    def NextAssignment(self, context, isBoth):
        if not context.space_data.edit_tree:
            return
        if isBoth:
            self.foundGoalSkOut0 = None
        self.foundGoalSkOut1 = None
        callPos = context.space_data.cursor_location
        for li in GetNearestNodes(context.space_data.edit_tree.nodes, callPos):
            nd = li.tg
            list_fgSksOut = GetNearestSockets(nd, callPos)[1]
            if not list_fgSksOut:
                continue
            if isBoth:
                for li in list_fgSksOut:
                    if (li.tg.type in set_skTypeFields)or(li.tg.type=='GEOMETRY'):
                        self.foundGoalSkOut0 = li
                        break
                StencilUnCollapseNode(nd, self.foundGoalSkOut0)
                break
            StencilUnCollapseNode(nd, self.foundGoalSkOut1) #todo1 ^ и v; кажется пришло время стандартизировать конвеер для всех инструментов!
            skOut0 = self.foundGoalSkOut0.tg if self.foundGoalSkOut0 else None
            if skOut0:
                if skOut0.type not in {'VALUE','INT','BOOLEAN'}:
                    break
                for li in list_fgSksOut:
                    if skOut0.type==li.tg.type:
                            self.foundGoalSkOut1 = li
                    if self.foundGoalSkOut1:
                        break
                if (self.foundGoalSkOut1)and(skOut0==self.foundGoalSkOut1.tg):
                    self.foundGoalSkOut1 = None
                    break
            if self.foundGoalSkOut1:
                break
    def modal(self, context, event):
        if StencilMouseNextAndReout(self, context, event, False, True):
            if result:=StencilModalEsc(self, context, event):
                return result
            if self.foundGoalSkOut0:
                skOut0 = self.foundGoalSkOut0.tg
                tree = context.space_data.edit_tree
                dict_qDM = dict_dictQuickDimensionsMain.get(tree.bl_idname, None)
                if not dict_qDM:
                    return {'CANCELLED'}
                isOutNdCol = skOut0.node.bl_idname==dict_qDM['RGBA'][0] #Заметка: нод разделения; на выходе всегда флоаты.
                isGeoTree = tree.bl_idname=='GeometryNodeTree'
                isOutNdQuat = (isGeoTree)and(skOut0.node.bl_idname==dict_qDM['ROTATION'][0])
                txt_node = dict_qDM[skOut0.type][isOutNdCol if not isOutNdQuat else 2]
                #Добавить:
                bpy.ops.node.add_node('INVOKE_DEFAULT', type=txt_node, use_transform=not self.isPlaceImmediately)
                aNd = tree.nodes.active
                aNd.width = 140
                if aNd.bl_idname in {dict_qDM['RGBA'][0], dict_qDM['VALUE'][1]}: #|5|.
                    aNd.show_options = False #Слишком неэстетично прятать без разбору, поэтому проверка выше.
                if skOut0.type in set_skTypeArrFields: #Зато экономия явных определений для каждого типа.
                    aNd.inputs[0].hide_value = True
                #Установить одинаковость модов (например, RGB и HSV):
                for li in GetListOfNdEnums(aNd):
                    if hasattr(skOut0.node, li.identifier):
                        setattr(aNd, li.identifier, getattr(skOut0.node, li.identifier))
                #Соединить:
                skIn = aNd.inputs[0]
                for ski in aNd.inputs:
                    if skOut0.name==ski.name:
                        skIn = ski
                        break
                NewLinkAndRemember(skOut0, skIn)
                if self.foundGoalSkOut1:
                    NewLinkAndRemember(self.foundGoalSkOut1.tg, aNd.inputs[1])
            return {'FINISHED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        if result:=UselessForCustomUndefTrees(context):
            return result
        if result:=StencilBeginToolInvoke(self, context, event):
            return result
        self.foundGoalSkOut0 = None
        self.foundGoalSkOut1 = None
        StencilToolWorkPrepare(self, context, CallbackDrawVoronoiQuickDimensions, True)
        return {'RUNNING_MODAL'}

SmartAddToRegAndAddToKmiDefs(VoronoiQuickDimensionsTool, "D_scA")
dict_setKmiCats['s'].add(VoronoiQuickDimensionsTool.bl_idname)

txt_victName = ""

def CallbackDrawVoronoiInterfaceCopier(self, context):
    if StencilStartDrawCallback(self, context):
        return
    cusorPos = context.space_data.cursor_location
    if self.foundGoalSk:
        DrawToolOftenStencil( self, cusorPos, [self.foundGoalSk], isLineToCursor=True, textSideFlip=True )
    elif self.prefs.dsIsDrawPoint:
        DrawWidePoint(self, cusorPos)
class VoronoiInterfaceCopierTool(VoronoiToolSkNd):
    bl_idname = 'node.voronoi_interface_copier'
    bl_label = "Voronoi Interface Copier"
    isPaste: bpy.props.BoolProperty(name="Paste", default=False)
    def NextAssignment(self, context, isBoth):
        if not context.space_data.edit_tree:
            return
        self.foundGoalSk = None
        if (not txt_victName)and(self.isPaste): #Ожидаемо; а ещё #113860.
            return
        callPos = context.space_data.cursor_location
        for li in GetNearestNodes(context.space_data.edit_tree.nodes, callPos):
            nd = li.tg
            if nd.type=='REROUTE':
                continue
            if (self.isPaste)and(nd.bl_idname not in set_equestrianPortalBlids): 
                break #Курсор должен быть рядом со всадником. А ещё с `continue` изменение интерфейса будет "неизбежно", и никак не отменить.
            if StencilUnCollapseNode(nd, isBoth):
                StencilReNext(self, context, True)
            #Далее облегчённый паттерн от VST, без sk.links и isBoth'а:
            list_fgSksIn, list_fgSksOut = GetNearestSockets(nd, callPos)
            fgSkOut, fgSkIn = None, None
            for li in list_fgSksOut:
                if li.tg.bl_idname!='NodeSocketVirtual':
                    fgSkOut = li
                    break
            for li in list_fgSksIn:
                if li.tg.bl_idname!='NodeSocketVirtual':
                    fgSkIn = li
                    break
            ##
            self.foundGoalSk = MinFromFgs(fgSkOut, fgSkIn)
            if self.foundGoalSk.tg.bl_idname=='NodeSocketVirtual': #todo2 ситуация, когда foundGoalSk == None
                continue
            if StencilUnCollapseNode(nd, self.foundGoalSk):
                StencilReNext(self, context, True)
            break
    def modal(self, context, event):
        if StencilMouseNextAndReout(self, context, event, False, True):
            if result:=StencilModalEsc(self, context, event):
                return result
            if self.foundGoalSk:
                global txt_victName
                sk = self.foundGoalSk.tg
                if self.isPaste:
                    #Такой же паттерн, как и в DoLinkHH.
                    ndEq = getattr(sk.node,'paired_output', sk.node)
                    match ndEq.bl_idname:
                        case 'NodeGroupOutput': typeEq = 0
                        case 'NodeGroupInput':  typeEq = 1
                        case 'GeometryNodeSimulationOutput': typeEq = 2
                        case 'GeometryNodeRepeatOutput':     typeEq = 3
                    match typeEq:
                        case 0|1:
                            skfi = ViaVerGetSkfi(context.space_data.edit_tree, not typeEq)
                        case 2:
                            skfi = ndEq.state_items
                        case 3:
                            skfi = ndEq.repeat_items
                    #Искать не по имени, а по identifier; ожидаемо почему.
                    for skf in skfi:
                        if skf.identifier==sk.identifier:
                            skf.name = txt_victName
                            break
                else:
                    txt_victName = sk.name
                return {'FINISHED'}
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        if result:=StencilBeginToolInvoke(self, context, event):
            return result
        self.foundGoalSk = None
        StencilToolWorkPrepare(self, context, CallbackDrawVoronoiInterfaceCopier, True)
        return {'RUNNING_MODAL'}

SmartAddToRegAndAddToKmiDefs(VoronoiInterfaceCopierTool, "C_ScA")
SmartAddToRegAndAddToKmiDefs(VoronoiInterfaceCopierTool, "V_ScA", {'isPaste':True})
dict_setKmiCats['s'].add(VoronoiInterfaceCopierTool.bl_idname)

def CallbackDrawVoronoiLinksTransfer(self, context):
    if StencilStartDrawCallback(self, context):
        return
    cusorPos = context.space_data.cursor_location
    #Паттерн VLT.
    if not self.foundGoalNdFrom:
        DrawDoubleNone(self, context)
    elif (self.foundGoalNdFrom)and(not self.foundGoalNdTo):
        DrawNodeStencilFull(self, cusorPos, self.foundGoalNdFrom, self.prefs.vhDrawNodeNameLabel, self.prefs.vhLabelDispalySide)
        if self.prefs.dsIsDrawPoint: #Точка под курсором шаблоном выше не обрабатывается, поэтому вручную.
            DrawWidePoint(self, cusorPos)
    else:
        DrawNodeStencilFull(self, cusorPos, self.foundGoalNdFrom, self.prefs.vhDrawNodeNameLabel, self.prefs.vhLabelDispalySide)
        DrawNodeStencilFull(self, cusorPos, self.foundGoalNdTo,   self.prefs.vhDrawNodeNameLabel, self.prefs.vhLabelDispalySide)
class VoronoiLinksTransferTool(VoronoiToolDblSk):
    bl_idname = 'node.voronoi_links_transfer'
    bl_label = "Voronoi Links Transfer"
    isByOrder: bpy.props.BoolProperty(name="Transfer by indexes", default=False)
    def NextAssignment(self, context, isBoth):
        if not context.space_data.edit_tree:
            return
        if isBoth:
            self.foundGoalNdFrom = None
        self.foundGoalNdTo = None
        callPos = context.space_data.cursor_location
        for li in GetNearestNodes(context.space_data.edit_tree.nodes, callPos):
            nd = li.tg
            if nd.type=='REROUTE':
                continue
            if isBoth:
                self.foundGoalNdFrom = li
            self.foundGoalNdTo = li
            if self.foundGoalNdFrom.tg==self.foundGoalNdTo.tg:
                self.foundGoalNdTo = None
            #Свершилось. Теперь у VL есть два нода.
            #Внезапно обнаружилось, что позиция "попадания" для нода буквально прилипает к нему, что весьма необычно наблюдать, когда тут вся тусовка ради сокетов.
            # Должна ли она скользить вместо прилипания?. Скорее всего нет, ведь иначе неизбежны осе-ориентированные проекции, визуально "затирающие" информацию.
            # А так же они оба будут изменяться, от чего не будет интуитивно понятно, кто первый, а кто второй; в отличие от прилипания, когда точно понятно, что "вот этот первый".
            # Что особенно актуально для этого инструмента, где важно, какой нод был выбран первым. #todo3 должен ли VLTT иметь эффект swapper'а?
            #if self.foundGoalNdFrom: #Если вдруг приспичит, то сделать из этого опцию рисования.
            #    self.foundGoalNdFrom.pos = GetNearestNode(self.foundGoalNdFrom.tg, callPos).pos
            break
    def modal(self, context, event):
        if StencilMouseNextAndReout(self, context, event, False, True):
            if result:=StencilModalEsc(self, context, event):
                return result
            if (self.foundGoalNdFrom)and(self.foundGoalNdTo):
                tree = context.space_data.edit_tree
                ndFrom = self.foundGoalNdFrom.tg
                ndTo = self.foundGoalNdTo.tg
                isFromInp = not event.alt
                LGetSide = lambda a: a.inputs if isFromInp else a.outputs
                if not self.isByOrder:
                    for sk in LGetSide(ndFrom):
                        for lk in sk.links: #Для мультиинпутов. #todo3 проверить корректность для всех ситуаций.
                            if not lk.is_muted:
                                skTar = LGetSide(ndTo).get(GetSkLabelName(sk))
                                if skTar:
                                    tree.links.new(lk.from_socket, skTar) if isFromInp else tree.links.new(skTar, lk.to_socket)
                                    if isFromInp: #todo3 Мультиинпуты! И придумать как это починить.
                                        tree.links.remove(lk)
                else:
                    LOnlyVisual = lambda a: [sk for sk in a if sk.enabled and not sk.hide]
                    for cyc, zp in enumerate(zip(LOnlyVisual(LGetSide(ndFrom)), LOnlyVisual(LGetSide(ndTo)))):
                        for lk in zp[0].links:
                            if not lk.is_muted:
                                tree.links.new(lk.from_socket, zp[1]) if isFromInp else tree.links.new(zp[1], lk.to_socket)
                                if isFromInp:
                                    tree.links.remove(lk)
                return {'FINISHED'}
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        if result:=StencilBeginToolInvoke(self, context, event):
            return result
        self.foundGoalNdFrom = None
        self.foundGoalNdTo = None
        StencilToolWorkPrepare(self, context, CallbackDrawVoronoiLinksTransfer, True)
        return {'RUNNING_MODAL'}

SmartAddToRegAndAddToKmiDefs(VoronoiLinksTransferTool, "T_sCa")
SmartAddToRegAndAddToKmiDefs(VoronoiLinksTransferTool, "T_SCa", {'isByOrder':True})
dict_setKmiCats['s'].add(VoronoiLinksTransferTool.bl_idname)

def CallbackDrawVoronoiWarper(self, context):
    if StencilStartDrawCallback(self, context):
        return
    cusorPos = context.space_data.cursor_location
    if self.foundGoalSkOut:
        DrawToolOftenStencil( self, cusorPos, [self.foundGoalSkOut], isLineToCursor=True, textSideFlip=True )
    elif self.prefs.dsIsDrawPoint:
        DrawWidePoint(self, cusorPos)
class VoronoiWarperTool(VoronoiToolSkNd):
    bl_idname = 'node.voronoi_warper'
    bl_label = "Voronoi Warper"
    isZoomedTo: bpy.props.BoolProperty(name="Zoom to", default=True)
    #isColorNodes: bpy.props.BoolProperty(name="Color nodes", default=False) #Тогда нужно будет париться с отчисткой, и цветом краски для разных тем. Лень, и наверное такое без нужды.
    def NextAssignment(self, context, *naArgs):
        if not context.space_data.edit_tree:
            return
        self.foundGoalSkOut = None
        callPos = context.space_data.cursor_location
        for li in GetNearestNodes(context.space_data.edit_tree.nodes, callPos):
            nd = li.tg
            if StencilUnCollapseNode(nd):
                StencilReNext(self, context, True)
            list_fgSksOut = GetNearestSockets(nd, callPos)[1]
            #Вариант для первого попавшегося сокета бер зарбору:
            #    self.foundGoalSkOut = list_fgSksOut[0] if list_fgSksOut else None
            #    break
            #Искать сокеты только с линками:
            for li in list_fgSksOut:
                if li.tg.links:
                    self.foundGoalSkOut = li
                    break
            if self.foundGoalSkOut:
                break
        if self.foundGoalSkOut:
            if StencilUnCollapseNode(self.foundGoalSkOut.tg.node):
                StencilReNext(self, context, True)
    def modal(self, context, event):
        if StencilMouseNextAndReout(self, context, event):
            if result:=StencilModalEsc(self, context, event):
                return result
            if self.foundGoalSkOut:
                sk = self.foundGoalSkOut.tg
                bpy.ops.node.select_all(action='DESELECT')
                if sk.links:
                    def RecrSelect(sk):
                        for lk in sk.links:
                            nd = lk.to_node
                            if nd.type=='REROUTE':
                                RecrSelect(nd.outputs[0])
                            nd.select = True #Рероуты наверное тоже стоит выделять.
                    RecrSelect(sk)
                    if event.alt: #Здесь; для новой возможности иметь клавишу в свойствах инструмента.
                        sk.node.select = True
                    sk.id_data.nodes.active = sk.node
                    if self.isZoomedTo:
                        bpy.ops.node.view_selected('INVOKE_DEFAULT')
                else:
                    sk.node.select = True
                    if self.isZoomedTo:
                        bpy.ops.node.view_selected('INVOKE_DEFAULT')
                    sk.node.select = False #Огонь хак.
                    #Изначально я ещё хотел максимально зумиться на сокет, но наверное это будет слишком странно; так что не стал.
                return {'FINISHED'}
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        if result:=StencilBeginToolInvoke(self, context, event):
            return result
        self.foundGoalSkOut = None
        StencilToolWorkPrepare(self, context, CallbackDrawVoronoiWarper, True)
        return {'RUNNING_MODAL'}

SmartAddToRegAndAddToKmiDefs(VoronoiWarperTool, "W_scA")
SmartAddToRegAndAddToKmiDefs(VoronoiWarperTool, "W_ScA", {'isZoomedTo':False})
dict_setKmiCats['s'].add(VoronoiWarperTool.bl_idname)

def CallbackDrawVoronoiLazyNodeStencils(self, context):
    if StencilStartDrawCallback(self, context):
        return
    cusorPos = context.space_data.cursor_location
    if not self.foundGoalSkFirst:
        DrawDoubleNone(self, context)
    elif (self.foundGoalSkFirst)and(not self.foundGoalSkSecond):
        DrawToolOftenStencil(self, cusorPos, [self.foundGoalSkFirst], isLineToCursor=True, textSideFlip=True)
        if self.prefs.dsIsDrawPoint:
            DrawWidePoint(self, cusorPos)
    else:
        DrawToolOftenStencil(self, cusorPos, [self.foundGoalSkFirst], isLineToCursor=True, isDrawText=False)
        DrawToolOftenStencil(self, cusorPos, [self.foundGoalSkSecond], isLineToCursor=True, isDrawText=False)
        if self.foundGoalSkFirst.tg.is_output^self.foundGoalSkSecond.tg.is_output:
            DrawMixerSkText(self, cusorPos, self.foundGoalSkFirst, -0.5, 0) #todo3 не очевидное соответствие стороне текста гендеру сокета.
            DrawMixerSkText(self, cusorPos, self.foundGoalSkSecond, -0.5, 0)
        else:
            DrawMixerSkText(self, cusorPos, self.foundGoalSkFirst, 0.25, -1)
            DrawMixerSkText(self, cusorPos, self.foundGoalSkSecond, -1.25, -1)
#Первый инструмент, что был создан по запросам извне, а не по моим личным хотелкам.
class VoronoiLazyNodeStencilsTool(VoronoiToolDblSk):
    bl_idname = 'node.voronoi_lazy_node_stencils'
    bl_label = "Voronoi Lazy Node Stencils" #Три буквы на инструмент, дожили.
    def NextAssignment(self, context, isBoth):
        def FindAnySk():
            fgSkOut, fgSkIn = None, None
            for li in list_fgSksOut:
                fgSkOut = li
                break
            for li in list_fgSksIn:
                fgSkIn = li
                break
            return MinFromFgs(fgSkOut, fgSkIn)
        if not context.space_data.edit_tree:
            return
        self.foundGoalSkSecond = None
        callPos = context.space_data.cursor_location
        #Из-за своего предназначения, этот инструмент гарантированно получает первый попавшийся сокет.
        for li in GetNearestNodes(context.space_data.edit_tree.nodes, callPos):
            nd = li.tg
            list_fgSksIn, list_fgSksOut = GetNearestSockets(nd, callPos)
            if isBoth:
                self.foundGoalSkFirst = FindAnySk()
            skFirst = self.foundGoalSkFirst.tg if self.foundGoalSkFirst else None
            if skFirst:
                if StencilUnCollapseNode(nd, isBoth):
                    StencilReNext(self, context, True)
                self.foundGoalSkSecond = FindAnySk()
                if self.foundGoalSkSecond:
                    if skFirst==self.foundGoalSkSecond.tg:
                        self.foundGoalSkSecond = None
                    if StencilUnCollapseNode(nd):
                        StencilReNext(self, context, False)
            break
    def modal(self, context, event):
        if StencilMouseNextAndReout(self, context, event, False, True):
            if result:=StencilModalEsc(self, context, event):
                return result
            if not(self.foundGoalSkFirst):
                return {'CANCELLED'}
            tree = context.space_data.edit_tree
            skFirst = self.foundGoalSkFirst.tg if self.foundGoalSkFirst else None
            skSecond = self.foundGoalSkSecond.tg if self.foundGoalSkSecond else None
            HhLazyStencil(context, tree, skFirst, skSecond)
            return {'FINISHED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        if result:=StencilBeginToolInvoke(self, context, event):
            return result
        self.foundGoalSkFirst = None
        self.foundGoalSkSecond = None
        self.isDrawDoubleNone = True
        StencilToolWorkPrepare(self, context, CallbackDrawVoronoiLazyNodeStencils, True)
        return {'RUNNING_MODAL'}

SmartAddToRegAndAddToKmiDefs(VoronoiLazyNodeStencilsTool, "Q_scA") #L_sca
dict_setKmiCats['s'].add(VoronoiLazyNodeStencilsTool.bl_idname)

#Внезапно оказалось, что моя когда-то идея для инструмента "Ленивое Продолжение" инкапсулировалось в этом инструменте. Вот так неожиданность.
#Этот инструмент тоже самое, как и ^ (где сокет и нод однозначно определял следующий нод), только для двух сокетов; и возможностей больше.

lzAny = '!any'
class LazyKey:
    def __init__(self, fnb, fst, fsn, fsg, snb=lzAny, sst=lzAny, ssn=lzAny, ssg=lzAny):
        self.firstNdBlid = fnb
        self.firstSkBlid = CollapseBlid(fst)
        self.firstSkName = fsn
        self.firstSkGend = fsg
        self.secondNdBlid = snb
        self.secondSkBlid = CollapseBlid(sst)
        self.secondSkName = ssn
        self.secondSkGend = ssg
class LazyNode:
    #Чёрная магия. Если в __init__(list_props=[]), то указание в одном nd.list_props += [..] меняет вообще у всех в lzSt. Нереально чёрная магия; ночные кошмары обеспечены.
    def __init__(self, blid, list_props, ofs=(0,0), hhoSk=0, hhiSk=0):
        self.blid = blid
        #list_props Содержит в себе обработку и сокетов тоже.
        #Указание на сокеты (в list_props и lzHh_Sk) -- +1 от индекса, а знак указывает сторону; => 0 не используется.
        self.list_props = list_props
        self.lzHhOutSk = hhoSk
        self.lzHhInSk = hhiSk
        self.locloc = ofs #"Local location"; и offset от центра мира.
class LazyStencil:
    def __init__(self, key, csn=2, name="", prior=0.0):
        self.lzkey = key
        self.prior = prior #Чем выше, тем важнее.
        self.name = name
        self.trees = {} #Это так же похоже на часть ключа.
        self.isTwoSkNeeded = csn==2
        self.list_nodes = []
        self.list_links = [] #Порядковый нод / сокет, и такое же на вход.
        self.isSameLink = False
        self.txt_exec = ""

list_lazyNodeStencilsDataPool = []

import copy
#Database:
lzSt = LazyStencil(LazyKey(lzAny,'RGB','Color',True,lzAny,'VECTOR','Normal',False), 2, "Fast Color NormapMap")
lzSt.trees = {'ShaderNodeTree'}
lzSt.list_nodes.append( LazyNode('ShaderNodeNormalMap', [], hhiSk=-2, hhoSk=1) )
lzSt.txt_exec = "skFirst.node.image.colorspace_settings.name = 'Non-Color'"
list_lazyNodeStencilsDataPool.append(lzSt)
##
lzSt = LazyStencil(LazyKey(lzAny,'RGB','Color',True,lzAny,'VALUE',lzAny,False), 2, "Lazy Non-Color data to float socket")
lzSt.trees = {'ShaderNodeTree'}
lzSt.isSameLink = True
lzSt.txt_exec = "skFirst.node.image.colorspace_settings.name = 'Non-Color'"
list_lazyNodeStencilsDataPool.append(lzSt)
##
lzSt = LazyStencil(LazyKey(lzAny,'RGB','Color',False), 1, "NW TexCord Parody")
lzSt.trees = {'ShaderNodeTree'}
lzSt.list_nodes.append( LazyNode('ShaderNodeTexImage', [(2,'hide',True)], hhoSk=-1) )
lzSt.list_nodes.append( LazyNode('ShaderNodeMapping', [(-1,'hide_value',True)], ofs=(-180,0)) )
lzSt.list_nodes.append( LazyNode('ShaderNodeUVMap', [('width',140)], ofs=(-360,0)) )
lzSt.list_links += [ (1,0,0,0),(2,0,1,0) ]
list_lazyNodeStencilsDataPool.append(lzSt)
lzSt = copy.deepcopy(lzSt)
lzSt.lzkey.firstSkName = "Base Color"
list_lazyNodeStencilsDataPool.append(lzSt)
##

list_lazyNodeStencilsDataPool.sort(key=lambda a: a.prior, reverse=True)

#Для одного нода ещё и сгодилось бы, но учитывая большое разнообразие и гибкость, наверное лучше без NewLinkAndRemember(), а в сыром виде.
def DoLazyStencil(tree, skFirst, skSecond, lzSten):
    list_result = []
    firstCenter = None
    for li in lzSten.list_nodes:
        nd = tree.nodes.new(li.blid)
        nd.location += mathutils.Vector(li.locloc)
        list_result.append(nd)
        for pr in li.list_props:
            if length(pr)==2:
                setattr(nd, pr[0], pr[1])
            else:
                setattr( (nd.outputs if pr[0]>0 else nd.inputs)[abs(pr[0])-1], pr[1], pr[2] )
        if li.lzHhOutSk:
            tree.links.new(nd.outputs[abs(li.lzHhOutSk)-1], skFirst if li.lzHhOutSk<0 else skSecond)
        if li.lzHhInSk:
            tree.links.new(skFirst if li.lzHhInSk<0 else skSecond, nd.inputs[abs(li.lzHhInSk)-1])
    for li in lzSten.list_links:
        tree.links.new(list_result[li[0]].outputs[li[1]], list_result[li[2]].inputs[li[3]])
    if lzSten.isSameLink:
        tree.links.new(skFirst, skSecond)
    return list_result
def LzCompare(a, b):
    return (a==b)or(a==lzAny)
def LzNodeDoubleCheck(zk, a, b): return LzCompare(zk.firstNdBlid,       a.bl_idname if a else "") and LzCompare(zk.secondNdBlid,       b.bl_idname if b else "")
def LzTypeDoubleCheck(zk, a, b): return LzCompare(zk.firstSkBlid, CollapseSkBlid(a) if a else "") and LzCompare(zk.secondSkBlid, CollapseSkBlid(b) if b else "") #Не 'type', а blid'ы; для аддонских деревьев.
def LzNameDoubleCheck(zk, a, b): return LzCompare(zk.firstSkName, GetSkLabelName(a) if a else "") and LzCompare(zk.secondSkName, GetSkLabelName(b) if b else "")
def LzGendDoubleCheck(zk, a, b): return LzCompare(zk.firstSkGend,       a.is_output if a else "") and LzCompare(zk.secondSkGend,       b.is_output if b else "")
def LazyStencil(tree, skFirst, skSecond):
    if not skFirst:
        return []
    ndOut = skFirst.node
    ndIn = skSecond.node if skSecond else None
    for li in list_lazyNodeStencilsDataPool:
        if (li.isTwoSkNeeded)^(not skSecond): #Должен не иметь второго для одного, или иметь для двух.
            if (not li.trees)or(tree.bl_idname in li.trees): #Должен поддерживать тип дерева.
                zk = li.lzkey
                if LzNodeDoubleCheck(zk, ndOut, ndIn): #Совпадение нод.
                    if LzTypeDoubleCheck(zk, skFirst, skSecond): #Совпадение Blid'ов сокетов.
                        if LzNameDoubleCheck(zk, skFirst, skSecond): #Имён/меток сокетов.
                            if LzGendDoubleCheck(zk, skFirst, skSecond): #Гендеров.
                                result = DoLazyStencil(tree, skFirst, skSecond, li)
                                if li.txt_exec:
                                    try: exec(li.txt_exec) #Тревога!1, А нет.. без паники, это внутренее. Всё ещё всё в безопасности.
                                    except: pass
                                return result
def HhLazyStencil(context, tree, skFirst, skSecond):
    cusorPos = context.space_data.cursor_location
    list_nodes = LazyStencil(tree, skFirst, skSecond)
    if list_nodes:
        bpy.ops.node.select_all(action='DESELECT')
        firstOffset = cusorPos-list_nodes[0].location
        for nd in list_nodes:
            nd.select = True
            nd.location += firstOffset
        bpy.ops.node.translate_attach('INVOKE_DEFAULT')

#Шаблон для быстрого и удобного добавления нового инструмента:
def CallbackDrawVoronoiDummy(self, context):
    if StencilStartDrawCallback(self, context):
        return
    cusorPos = context.space_data.cursor_location
    if self.foundGoalSk:
        DrawToolOftenStencil( self, cusorPos, [self.foundGoalSk], isLineToCursor=True, textSideFlip=True )
    elif self.prefs.dsIsDrawPoint:
        DrawWidePoint(self, cusorPos)
class VoronoiDummyTool(VoronoiToolSkNd):
    bl_idname = 'node.voronoi_dummy'
    bl_label = "Voronoi Dummy"
    isDummy: bpy.props.BoolProperty(name="Dummy", default=False)
    def NextAssignment(self, context, isBoth):
        if not context.space_data.edit_tree:
            return
        self.foundGoalSk = None
        callPos = context.space_data.cursor_location
        for li in GetNearestNodes(context.space_data.edit_tree.nodes, callPos):
            nd = li.tg
            if StencilUnCollapseNode(nd, isBoth):
                StencilReNext(self, context, True)
            if nd.type=='REROUTE':
                continue
            list_fgSksIn, list_fgSksOut = GetNearestSockets(nd, callPos)
            fgSkIn = list_fgSksIn[0] if list_fgSksIn else None
            fgSkOut = list_fgSksOut[0] if list_fgSksOut else None
            self.foundGoalSk = MinFromFgs(fgSkOut, fgSkIn)
            break
        #todo3 навести здесь порядок и осознать всё повторно.
        if self.foundGoalSk:
            if StencilUnCollapseNode(self.foundGoalSk.tg.node):
                StencilReNext(self, context, True)
    def modal(self, context, event):
        if StencilMouseNextAndReout(self, context, event, False, True):
            if result:=StencilModalEsc(self, context, event):
                return result
            if self.foundGoalSk:
                sk = self.foundGoalSk.tg
                #print(GetSkLocVec(sk))
                sk.name = "hi. i am a vdt!"
                sk.node.label = "see source code"
                RememberLastSockets(sk if sk.is_output else None, sk if not sk.is_output else None)
                return {'FINISHED'}
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        if result:=StencilBeginToolInvoke(self, context, event):
            return result
        self.foundGoalSk = None
        StencilToolWorkPrepare(self, context, CallbackDrawVoronoiDummy, True)
        return {'RUNNING_MODAL'}

#SmartAddToRegAndAddToKmiDefs(VoronoiDummyTool, "D_sca", {'isDummy':True})
dict_setKmiCats['g'].add(VoronoiDummyTool.bl_idname)

def VLAddonVer():
    return "v"+".".join([str(v) for v in bl_info['version']])

def GetVlKeyconfigAsPy(): #Взято из `bl_keymap_utils.io`. Понятия не имею, как оно работает.
    import bl_keymap_utils
    def Ind(num):
        return " "*num
    def keyconfig_merge(kc1, kc2):
        kc1_names = {km.name for km in kc1.keymaps}
        merged_keymaps = [(km, kc1) for km in kc1.keymaps]
        if kc1 != kc2:
            merged_keymaps.extend(
                (km, kc2)
                for km in kc2.keymaps
                if km.name not in kc1_names)
        return merged_keymaps
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.active
    class FakeKeyConfig:
        keymaps = []
    edited_kc = FakeKeyConfig()
    edited_kc.keymaps.append(GetUserKmNe())
    if kc!=wm.keyconfigs.default:
        export_keymaps = keyconfig_merge(edited_kc, kc)
    else:
        export_keymaps = keyconfig_merge(edited_kc, edited_kc)
    ##
    result = ""
    result += "list_keyconfigData = \\\n["
    for km, _kc_x in export_keymaps:
        km = km.active()
        result += "("
        result += f"\"{km.name:s}\","+"\n"
        result += f"{Ind(2)}" "{"
        result += f"\"space_type\": '{km.space_type:s}'"
        result += f", \"region_type\": '{km.region_type:s}'"
        isModal = km.is_modal
        if isModal:
            result += ", \"modal\": True"
        result += "},"+"\n"
        result += f"{Ind(2)}" "{"
        result += f"\"items\":"+"\n"
        result += f"{Ind(3)}["
        for kmi in km.keymap_items:
            if not kmi.idname.startswith("node.voronoi_"):
                continue
            if isModal:
                kmi_id = kmi.propvalue
            else:
                kmi_id = kmi.idname
            result += f"("
            kmi_args = bl_keymap_utils.io.kmi_args_as_data(kmi)
            kmi_data = bl_keymap_utils.io._kmi_attrs_or_none(4, kmi)
            result += f"\"{kmi_id:s}\""
            if kmi_data is None:
                result += f", "
            else:
                result += ",\n" f"{Ind(5)}"
            result += kmi_args
            if kmi_data is None:
                result += ", None),"+"\n"
            else:
                result += ","+"\n"
                result += f"{Ind(5)}" "{"
                result += kmi_data
                result += f"{Ind(6)}"
                result += "},\n" f"{Ind(5)}"
                result += "),"+"\n"
            result += f"{Ind(4)}"
        result += "],\n" f"{Ind(3)}"
        result += "},\n" f"{Ind(2)}"
        result += "),\n" f"{Ind(1)}"
    result += "]"+"\n"
    result += "\n"
    result += "if True:"+"\n"
    result += "    import bl_keymap_utils"+"\n"
    result += "    import bl_keymap_utils.versioning"+"\n" #Чёрная магия; кажется, такая же как и с "gpu_extras".
    result += "    #\n"
    result += "    kc = bpy.context.window_manager.keyconfigs.active"+"\n"
    from bpy.app import version_file
    result += f"    kd = bl_keymap_utils.versioning.keyconfig_update(list_keyconfigData, {version_file!r})"+"\n"
    del version_file
    result += "    bl_keymap_utils.io.keyconfig_init_from_data(kc, kd)"
    return result

def GetVaSettAsPy(isAllPrefs=True):
    txt_vasp = ""
    import datetime
    txt_vasp += f"#Exported/Importing addon settings for Voronoi Linker {VLAddonVer()}\n"
    txt_vasp += f"#Generated "+datetime.datetime.now().strftime("%Y.%m.%d")+"\n"
    txt_vasp += "\n"
    txt_vasp += "import bpy\n"
    set_ignoredAddonPrefs = {'bl_idname', 'vaUiTabs', 'vaInfoRestore', 'vaShowAddonOptions', 'vaShowAllToolsOptions',
            'vaKmiMainstreamBoxDiscl', 'vaKmiOtjersBoxDiscl', 'vaKmiSpecialBoxDiscl', 'vaKmiQqmBoxDiscl', 'vaKmiCustomBoxDiscl'}
    #Сконструировать изменённые настройки аддона:
    txt_vasp += "\n"
    txt_vasp += "#Addon prefs:\n"
    txt_vasp += f"prefs = bpy.context.preferences.addons['{voronoiAddonName}'].preferences"+"\n\n"
    prefs = Prefs()
    for li in prefs.rna_type.properties:
        if not li.is_readonly:
            #'_BoxDiscl'ы не стал игнорировать, пусть будут.
            if li.identifier not in set_ignoredAddonPrefs:
                isArray = getattr(li,'is_array', False)
                if isArray:
                    isDiff = not not [li for li in zip(li.default_array, getattr(prefs, li.identifier)) if li[0]!=li[1]]
                else:
                    isDiff = li.default!=getattr(prefs, li.identifier)
                if (isDiff)or(isAllPrefs):
                    if isArray:
                        #txt_vasp += f"prefs.{li.identifier} = ({' '.join([str(li)+',' for li in arr])})\n"
                        list_vals = [str(li)+"," for li in getattr(prefs, li.identifier)]
                        list_vals[-1] = list_vals[-1][:-1]
                        txt_vasp += f"prefs.{li.identifier} = ("+" ".join(list_vals)+")\n"
                    else:
                        match li.type:
                            case 'STRING': txt_vasp += f"prefs.{li.identifier} = \"{getattr(prefs, li.identifier)}\""+"\n"
                            case 'ENUM':   txt_vasp += f"prefs.{li.identifier} = '{getattr(prefs, li.identifier)}'"+"\n"
                            case _:        txt_vasp += f"prefs.{li.identifier} = {getattr(prefs, li.identifier)}"+"\n"
    #Сконструировать все VL хоткеи:
    txt_vasp += "\n"
    txt_vasp += "#Addon keymaps:\n"
    #P.s. я не знаю, как обрабатывать только изменённые хоткеи; это выглядит слишком головной болью и дремучим лесом.
    # Лень реверсинженерить '..\scripts\modules\bl_keymap_utils\io.py', поэтому просто сохранять всех.
    txt_vasp += GetVlKeyconfigAsPy() #Оно нахрен не работает. Та часть, которая восстанавливает. Ничего не сохраняется.
    #Придётся ждать того героя, что придёт и починит всё это.
    #todo1 нужно придумать другой способ сохранения хоткеев.
    return txt_vasp

#Здесь оставлю мой маленький список моих "хотелок", который перекачевали из других моих личных аддонов в VL:
#Hider, QuckMath и JustMathPie, Warper

#todo1 мб стоит как-нибудь заменить "сосался" на более адекватное "цеплялся".

def Prefs():
    return bpy.context.preferences.addons[voronoiAddonName].preferences

voronoiTextToolSettings = " Tool settings:"
txt_onlyFontFormat = "Only .ttf or .otf format"
txt_copySettAsPyScript = "Copy addon settings as .py script"

set_ignoredAddonPrefs = {'bl_idname', 'vaUiTabs', 'vaInfoRestore', 'vaShowAddonOptions', 'vaShowAllToolsOptions',
                                      'vaKmiMainstreamBoxDiscl', 'vaKmiOtjersBoxDiscl', 'vaKmiSpecialBoxDiscl', 'vaKmiQqmBoxDiscl', 'vaKmiCustomBoxDiscl'}
class VoronoiAddonTabs(bpy.types.Operator):
    bl_idname = 'node.voronoi_addon_tabs'
    bl_label = "VL Addon Tabs"
    opt: bpy.props.StringProperty()
    def invoke(self, context, event):
        match self.opt:
            case 'GetPySett':
                context.window_manager.clipboard = GetVaSettAsPy(isAllPrefs=event.shift or True) #Наверное бесполезно иметь разницу.
                # Особенно чем дальше в будущее, когда будут удаляться и появляться новые настройки.
            case 'AddNewKmi':
                GetUserKmNe().keymap_items.new("node.voronoi_",'D','PRESS').show_expanded = True
            case _:
                Prefs().vaUiTabs = self.opt
        return {'FINISHED'}
class KmiCat:
    def __init__(self, txt_prop='', label="", set_kmis=set(), sco=0, set_idn=set()):
        self.txt_prop = txt_prop
        self.set_kmis = set_kmis
        self.set_idn = set_idn
        self.label = label
        self.sco = sco
class KmiCats:
    pass
class VoronoiAddonPrefs(bpy.types.AddonPreferences):
    bl_idname = voronoiAddonName if __name__=="__main__" else __name__
    #AddonPrefs
    vaUiTabs: bpy.props.EnumProperty(name="Addon Prefs Tabs", default='SETTINGS', items=( ('SETTINGS',"Settings",""),
                                                                                          ('DRAW',    "Draw",    ""),
                                                                                          ('KEYMAP',  "Keymap",  "") ))
    vaShowAddonOptions: bpy.props.BoolProperty(name="VL Addon:", default=False)
    vaShowAllToolsOptions: bpy.props.BoolProperty(name="All"+voronoiTextToolSettings, default=True) #todo2 наверное нужно переименовать.
    vaInfoRestore: bpy.props.BoolProperty(name="", description="This list is just a copy from the \"Preferences > Keymap\".\nResrore will restore everything \"Node Editor\", not just addon")
    #Box disclosures:
    vlBoxDiscl: bpy.props.BoolProperty(name="", default=True)
    vpBoxDiscl: bpy.props.BoolProperty(name="", default=True)
    vmBoxDiscl: bpy.props.BoolProperty(name="", default=True)
    vqmBoxDiscl: bpy.props.BoolProperty(name="", default=True)
    vsBoxDiscl: bpy.props.BoolProperty(name="", default=True)
    vhBoxDiscl: bpy.props.BoolProperty(name="", default=True)
    vesBoxDiscl: bpy.props.BoolProperty(name="", default=True)
    ##
    vaKmiMainstreamBoxDiscl: bpy.props.BoolProperty(name="", default=True)
    vaKmiOtjersBoxDiscl:     bpy.props.BoolProperty(name="", default=True)
    vaKmiSpecialBoxDiscl:    bpy.props.BoolProperty(name="", default=True)
    vaKmiQqmBoxDiscl:        bpy.props.BoolProperty(name="", default=True)
    vaKmiCustomBoxDiscl:     bpy.props.BoolProperty(name="", default=True)
    #Draw
    dsIsDrawText:   bpy.props.BoolProperty(name="Text",        default=True) #Учитывая VHT и VEST, это уже больше просто для текста в рамке, чем для текста от сокетов.
    dsIsDrawMarker: bpy.props.BoolProperty(name="Markers",     default=True)
    dsIsDrawPoint:  bpy.props.BoolProperty(name="Points",      default=True)
    dsIsDrawLine:   bpy.props.BoolProperty(name="Line",        default=True)
    dsIsDrawSkArea: bpy.props.BoolProperty(name="Socket area", default=True)
    ##
    dsIsColoredText:   bpy.props.BoolProperty(name="Text",        default=True)
    dsIsColoredMarker: bpy.props.BoolProperty(name="Markers",     default=True)
    dsIsColoredPoint:  bpy.props.BoolProperty(name="Points",      default=True)
    dsIsColoredLine:   bpy.props.BoolProperty(name="Line",        default=True)
    dsIsColoredSkArea: bpy.props.BoolProperty(name="Socket area", default=True)
    ##
    dsIsAlwaysLine:    bpy.props.BoolProperty(       name="Always draw line",          default=False)
    dsSocketAreaAlpha: bpy.props.FloatProperty(      name="Socket area alpha",         default=0.075,                               min=0, max=1,         subtype="FACTOR")
    dsUniformColor:    bpy.props.FloatVectorProperty(name="Alternative uniform color", default=(0.632502, 0.408091, 0.174378, 0.9), min=0, max=1, size=4, subtype='COLOR') #(0.65, 0.65, 0.65, 1.0)
    dsNodeColor:       bpy.props.FloatVectorProperty(name="To-Node draw color",        default=(1.0, 1.0, 1.0, 0.9),                min=0, max=1, size=4, subtype='COLOR')
    ##
    dsDisplayStyle: bpy.props.EnumProperty(name="Display frame style", default='CLASSIC', items=( ('CLASSIC',   "Classic",   "1"), #Если существует способ указать порядок
                                                                                                  ('SIMPLIFIED',"Simplified","2"), # и чтобы работало -- дайте знать.
                                                                                                  ('ONLYTEXT',  "Only text", "3") ))
    dsFontFile:    bpy.props.StringProperty(name="Font file",  default='C:\Windows\Fonts\consola.ttf', subtype='FILE_PATH') #"Пользователи Линукса негодуют".
    dsLineWidth:   bpy.props.FloatProperty( name="Line Width", default=1.25, min=0.5, max=16, subtype="FACTOR")
    dsPointRadius: bpy.props.FloatProperty( name="Point size", default=1,    min=0,   max=3)
    dsFontSize:    bpy.props.IntProperty(   name="Font size",  default=28,   min=10,  max=48)
    ##
    dsPointOffsetX:   bpy.props.FloatProperty(name="Point offset X axis",       default=20, min=-50, max=50)
    dsFrameOffset:    bpy.props.IntProperty(  name="Frame size",                default=0,  min=0,   max=24, subtype='FACTOR')
    dsDistFromCursor: bpy.props.FloatProperty(name="Text distance from cursor", default=25, min=5,   max=50)
    ##
    dsIsAllowTextShadow: bpy.props.BoolProperty(       name="Enable text shadow", default=True)
    dsShadowCol:         bpy.props.FloatVectorProperty(name="Shadow color",       default=[0.0, 0.0, 0.0, 0.5], size=4, min=0,   max=1, subtype='COLOR')
    dsShadowOffset:      bpy.props.IntVectorProperty(  name="Shadow offset",      default=[2,-2],               size=2, min=-20, max=20)
    dsShadowBlur:        bpy.props.IntProperty(        name="Shadow blur",        default=2,                            min=0,   max=2)
    ##
    dsIsDrawDebug:  bpy.props.BoolProperty(name="Display debugging", default=False)
    # =====================================================================================================================================================
    #Main:
    #Уж было я хотел добавить это, но потом мне стало таак лень. Это же нужно всё менять под "только сокеты", и критерии для нод неведомо как получать.
    #И выгода неизвестно какая, кроме эстетики. Так что ну его нахрен. Работает -- не трогай.
    #А ещё см. |4|, реализация "только сокеты" грозит потенциальной кроличьей норой.
    vtSearchMethod: bpy.props.EnumProperty(name="Search method", default='SOCKET', items=( ('NODE_SOCKET', "Nearest node > nearest socket", ""), #Нигде не используется.
                                                                                           ('SOCKET',      "Only nearest socket",           "") )) #И кажется, никогда не будет.
    vtRepickTrigger: bpy.props.EnumProperty(name="Repick trigger", default='ANY', items=( ('FULL', "Сomplete match of call modifiers", ""),
                                                                                          ('ANY',  "At least one of modifiers",        "") ))
    #Linker:
    vlReroutesCanInAnyType: bpy.props.BoolProperty(name="Reroutes can be connected to any type",  default=True)
    vlDeselectAllNodes:     bpy.props.BoolProperty(name="Deselect all nodes on activate",         default=False)
    vlAnnoyingIgnoring:     bpy.props.BoolProperty(name="Annoying ignoring",                      default=True) #Скорее всего придётся переименовать в что-то типа "приоритетное игнорирование".
    #Preview:
    vpAllowClassicCompositorViewer: bpy.props.BoolProperty(name="Allow classic Compositor Viewer", default=False)
    vpAllowClassicGeoViewer:        bpy.props.BoolProperty(name="Allow classic GeoNodes Viewer",   default=True)
    vpIsLivePreview: bpy.props.BoolProperty(name="Live preview", default=True)
    vpRvEeIsColorOnionNodes:    bpy.props.BoolProperty(name="Node onion colors",               default=False)
    vpRvEeSksHighlighting:      bpy.props.BoolProperty(name="Topology connected highlighting", default=False) #Ну и словечко. Три трио комбо. Выглядит как случайные удары по клавиатуре.
    vpRvEeIsSavePreviewResults: bpy.props.BoolProperty(name="Save preview results",            default=False)
    #Mixer:
    vmReroutesCanInAnyType: bpy.props.BoolProperty(name="Reroutes can be mixed to any type", default=True)
    vmPieType: bpy.props.EnumProperty(name="Pie Type", default='CONTROL', items=( ('SPEED',  "Speed",  ""),
                                                                                  ('CONTROL',"Control","") ))
    vmPieScale:             bpy.props.FloatProperty(name="Pie scale",                  default=1.5, min=1, max=2, subtype="FACTOR")
    vmPieSocketDisplayType: bpy.props.IntProperty(  name="Display socket type info",   default=1,   min=-1, max=1)
    vmPieAlignment:         bpy.props.IntProperty(  name="Alignment between elements", default=1,   min=0, max=2)
    #Quick math:
    vqmPieType: bpy.props.EnumProperty(name="Pie Type", default='CONTROL', items=( ('SPEED',  "Speed",  ""),
                                                                                   ('CONTROL',"Control","") ))
    vqmPieScale:             bpy.props.FloatProperty(name="Pie scale",                  default=1.5, min=1, max=2, subtype="FACTOR")
    vqmPieSocketDisplayType: bpy.props.IntProperty(  name="Display socket type info",   default=1,   min=0, max=2)
    vqmPieAlignment:         bpy.props.IntProperty(  name="Alignment between elements", default=1,   min=0, max=2)
    #Hider:
    vhNeverHideGeometry: bpy.props.EnumProperty(name="Never hide input geometry socket", default='FALSE', items=( ('FALSE',     "False",     ""),
                                                                                                                  ('ONLY_FIRST',"Only first",""),
                                                                                                                  ('TRUE',      "True",      "") ))
    vhHideBoolSocket: bpy.props.EnumProperty(name="Hide boolean sockets", default='IF_FALSE', items=( ('ALWAYS',  "Always",  ""),
                                                                                                      ('IF_FALSE',"If false",""),
                                                                                                      ('NEVER',   "Never",   ""),
                                                                                                      ('IF_TRUE', "If true", "") ))
    vhHideHiddenBoolSocket: bpy.props.EnumProperty(name="Hide hidden boolean sockets", default='ALWAYS', items=( ('ALWAYS',  "Always",  ""),
                                                                                                                 ('IF_FALSE',"If false",""),
                                                                                                                 ('NEVER',   "Never",   ""),
                                                                                                                 ('IF_TRUE', "If true", "") ))
    vhIsUnhideVirtual:     bpy.props.BoolProperty(name="Unhide virtual",       default=False)
    vhIsToggleNodesOnDrag: bpy.props.BoolProperty(name="Toggle nodes on drag", default=True)
    vhDrawNodeNameLabel:   bpy.props.EnumProperty(name="Display text for node", default='NONE', items=( ('NONE',     "None",          ""),
                                                                                                        ('NAME',     "Only name",     ""),
                                                                                                        ('LABEL',    "Only label",    ""),
                                                                                                        ('LABELNAME',"Name and label","") ))
    vhLabelDispalySide: bpy.props.IntProperty(name="Label Dispaly Side", default=3, min=1, max=4) #Настройка выше и так какая-то бесполезная, а эта прям ваще.
    #Enum selector:
    vesIsToggleNodesOnDrag: bpy.props.BoolProperty(name="Toggle nodes on drag", default=True)
    vesIsInstantActivation: bpy.props.BoolProperty(name="Instant activation",   default=True)
    vesIsDrawEnumNames:     bpy.props.BoolProperty(name="Draw enum names",      default=False)
    vesDrawNodeNameLabel:   bpy.props.EnumProperty(name="Display text for node", default='NONE', items=( ('NONE',     "None",          ""),
                                                                                                         ('NAME',     "Only name",     ""),
                                                                                                         ('LABEL',    "Only label",    ""),
                                                                                                         ('LABELNAME',"Name and label","") ))
    vesLabelDispalySide: bpy.props.IntProperty(name="Label Dispaly Side",  default=3,   min=1, max=4) #Так же, как и для VHT.
    vesBoxScale:         bpy.props.FloatProperty(name="Box scale",         default=1.5, min=1, max=2, subtype="FACTOR")
    vesDisplayLabels:    bpy.props.BoolProperty(name="Display enum names", default=True)
    vesDarkStyle:        bpy.props.BoolProperty(name="Dark style",         default=False)
    ##
    def AddDisclosureProp(self, where, who, txt_prop, txt_text=None, isActive=False, txt_suffIfActive="", isWide=False): #Не может на всю ширину, если where -- row().
        tgl = getattr(who, txt_prop)
        row = where.row(align=True)
        row.alignment = 'LEFT'
        txt_text = txt_text+txt_suffIfActive*tgl if txt_text else None
        row.prop(who, txt_prop, text=txt_text, icon='DISCLOSURE_TRI_DOWN' if tgl else 'DISCLOSURE_TRI_RIGHT', emboss=False)
        row.active = isActive
        if isWide:
            row = row.row(align=True)
            row.prop(who, txt_prop, text=" ", emboss=False)
        return tgl
    def AddHandSplitProp(self, where, txt_prop, tgl=True, isReturnLy=False):
        spl = where.row().split(factor=0.38, align=True)
        spl.active = tgl
        row = spl.row(align=True)
        row.alignment = 'RIGHT'
        prop = self.rna_type.properties[txt_prop]
        isNotBool = prop.type!='BOOLEAN'
        row.label(text=prop.name*isNotBool)
        if (not tgl)and(prop.type=='FLOAT')and(prop.subtype=='COLOR'):
            box = spl.box()
            box.label()
            box.scale_y = 0.5
            row.active = False
        else:
            if not isReturnLy:
                spl.prop(self, txt_prop, text="" if isNotBool else None)
            else:
                return spl
    def DrawTabSettings(self, context, where):
        AddHandSplitProp = self.AddHandSplitProp
        def FastBox(where):
            return where.box().column(align=True)
        def AddSelfBoxDiscl(where, txt_prop, cls=None):
            colBox = FastBox(where)
            if self.AddDisclosureProp(colBox, self, txt_prop, (cls.bl_label+voronoiTextToolSettings) if cls else None):
                rowTool = colBox.row()
                rowTool.separator()
                colTool = rowTool.column(align=True)
                return colTool
            return None
        colMaster = where.column()
        try:
            def LeftProp(where, who, txt_prop):
                if True:
                    row = where.row()
                    row.alignment = 'LEFT'
                    row.prop(who, txt_prop)
                else:
                    where.prop(who, txt_prop)
            if colTool:=AddSelfBoxDiscl(colMaster,'vaShowAllToolsOptions'):
                #colTool.prop(self,'vtSearchMethod')
                colTool.prop(self,'vtRepickTrigger')
            if colTool:=AddSelfBoxDiscl(colMaster,'vlBoxDiscl', VoronoiLinkerTool):
                LeftProp(colTool, self,'vlReroutesCanInAnyType')
                LeftProp(colTool, self,'vlDeselectAllNodes')
                LeftProp(colTool, self,'vlAnnoyingIgnoring')
            if colTool:=AddSelfBoxDiscl(colMaster,'vpBoxDiscl', VoronoiPreviewTool):
                LeftProp(colTool, self,'vpIsLivePreview')
                colProps = FastBox(colTool)
                LeftProp(colProps, self,'vpAllowClassicCompositorViewer')
                LeftProp(colProps, self,'vpAllowClassicGeoViewer')
                LeftProp(colTool, self,'vpRvEeIsColorOnionNodes')
                LeftProp(colTool, self,'vpRvEeIsSavePreviewResults')
                LeftProp(colTool, self,'vpRvEeSksHighlighting')
            if colTool:=AddSelfBoxDiscl(colMaster,'vmBoxDiscl', VoronoiMixerTool):
                LeftProp(colTool, self,'vmReroutesCanInAnyType')
                AddHandSplitProp(colTool,'vmPieType')
                colProp = colTool.column(align=True)
                AddHandSplitProp(colProp,'vmPieScale')
                AddHandSplitProp(colProp,'vmPieSocketDisplayType')
                AddHandSplitProp(colProp,'vmPieAlignment')
                colProp.active = self.vmPieType=='CONTROL'
            if colTool:=AddSelfBoxDiscl(colMaster,'vqmBoxDiscl', VoronoiQuickMathTool):
                colTool.separator()
                AddHandSplitProp(colTool,'vqmPieType')
                colProp = colTool.column(align=True)
                AddHandSplitProp(colProp,'vqmPieScale')
                AddHandSplitProp(colProp,'vqmPieSocketDisplayType')
                AddHandSplitProp(colProp,'vqmPieAlignment')
                colProp.active = self.vqmPieType=='CONTROL'
            if colTool:=AddSelfBoxDiscl(colMaster,'vhBoxDiscl', VoronoiHiderTool):
                AddHandSplitProp(colTool,'vhHideBoolSocket')
                AddHandSplitProp(colTool,'vhHideHiddenBoolSocket')
                AddHandSplitProp(colTool,'vhNeverHideGeometry')
                LeftProp(colTool, self,'vhIsUnhideVirtual')
                LeftProp(colTool, self,'vhIsToggleNodesOnDrag')
                colProp = colTool.column(align=True)
                colProp.active = self.vhIsToggleNodesOnDrag
                colTool.separator()
                AddHandSplitProp(colTool,'vhDrawNodeNameLabel')
                colProp = colTool.column(align=True)
                AddHandSplitProp(colProp,'vhLabelDispalySide')
                colProp.active = self.vhDrawNodeNameLabel=='LABELNAME'
            if colTool:=AddSelfBoxDiscl(colMaster,'vesBoxDiscl', VoronoiEnumSelectorTool):
                LeftProp(colTool, self,'vesIsToggleNodesOnDrag')
                colProp = colTool.column(align=True)
                colProp.active = self.vesIsToggleNodesOnDrag
                AddHandSplitProp(colTool,'vesBoxScale')
                AddHandSplitProp(colTool,'vesDisplayLabels')
                AddHandSplitProp(colTool,'vesDarkStyle')
                LeftProp(colTool, self,'vesIsInstantActivation')
                colToolBox = colTool.column(align=True)
                #colToolBox.active = not self.vesIsInstantActivation #Я забыл что у VEST есть isToggleOptions, который рисует к нодам.
                AddHandSplitProp(colToolBox,'vesIsDrawEnumNames')
                colProp = colToolBox.column(align=True)
                colProp.active = not self.vesIsDrawEnumNames
                AddHandSplitProp(colProp,'vesDrawNodeNameLabel')
                colProp = colProp.column(align=True)
                AddHandSplitProp(colProp,'vesLabelDispalySide')
                colProp.active = self.vesDrawNodeNameLabel=='LABELNAME'
            if colTool:=AddSelfBoxDiscl(colMaster,'vaShowAddonOptions'):
                colProp = colTool.column(align=True)
                colProp.alignment = 'CENTER' #Всё равно 'LEFT'.
                colProp.scale_x = 1.15
                colProp.operator(VoronoiAddonTabs.bl_idname, text=txt_copySettAsPyScript).opt = 'GetPySett'
        except Exception as ex:
            colMaster.label(text=str(ex), icon='ERROR')
    def DrawTabDraw(self, context, where):
        AddHandSplitProp = self.AddHandSplitProp
        colMaster = where.column()
        try:
            rowDrawColor = colMaster.row(align=True)
            rowDrawColor.use_property_split = True
            colDraw = rowDrawColor.column(align=True, heading='Draw')
            colDraw.prop(self,'dsIsDrawText')
            colDraw.prop(self,'dsIsDrawMarker')
            colDraw.prop(self,'dsIsDrawPoint')
            colDraw.prop(self,'dsIsDrawLine')
            colDraw.prop(self,'dsIsDrawSkArea')
            colCol = rowDrawColor.column(align=True, heading='Colored')
            def AddColoredProp(where, txt):
                row = where.row(align=True)
                row.prop(self, txt)
                row.active = getattr(self, txt.replace("Colored","Draw"))
            AddColoredProp(colCol,'dsIsColoredText')
            AddColoredProp(colCol,'dsIsColoredMarker')
            AddColoredProp(colCol,'dsIsColoredPoint')
            AddColoredProp(colCol,'dsIsColoredLine')
            AddColoredProp(colCol,'dsIsColoredSkArea')
            colProps = colMaster.column()
            AddHandSplitProp(colProps, 'dsIsAlwaysLine')
            AddHandSplitProp(colProps, 'dsSocketAreaAlpha')
            tgl = ( (self.dsIsDrawText and not self.dsIsColoredText)or
                    (self.dsIsDrawMarker and not self.dsIsColoredMarker)or
                    (self.dsIsDrawPoint  and not self.dsIsColoredPoint )or
                    (self.dsIsDrawLine   and not self.dsIsColoredLine  )or
                    (self.dsIsDrawSkArea and not self.dsIsColoredSkArea) )
            AddHandSplitProp(colProps, 'dsUniformColor', tgl)
            tgl = ( (self.dsIsDrawText and self.dsIsColoredText)or
                    (self.dsIsDrawPoint  and self.dsIsColoredPoint )or
                    (self.dsIsDrawLine   and self.dsIsColoredLine  ) )
            AddHandSplitProp(colProps, 'dsNodeColor', tgl)
            AddHandSplitProp(colProps, 'dsDisplayStyle')
            AddHandSplitProp(colProps, 'dsFontFile')
            import os
            if not os.path.splitext(self.dsFontFile)[1] in (".ttf",".otf"):
                spl = colProps.split(factor=0.4, align=True)
                spl.label(text="")
                spl.label(text=txt_onlyFontFormat, icon='ERROR')
            colGroup = colProps.column(align=True)
            AddHandSplitProp(colGroup, 'dsLineWidth')
            AddHandSplitProp(colGroup.row(), 'dsPointRadius')
            AddHandSplitProp(colGroup, 'dsFontSize')
            row = colProps.row(align=True)
            row.separator()
            row.scale_x = .333
            colGroup = colProps.column(align=True)
            AddHandSplitProp(colGroup, 'dsPointOffsetX')
            AddHandSplitProp(colGroup.row(), 'dsFrameOffset')
            AddHandSplitProp(colGroup, 'dsDistFromCursor')
            AddHandSplitProp(colProps, 'dsIsAllowTextShadow')
            colShadow = colProps.column(align=True)
            AddHandSplitProp(colShadow, 'dsShadowCol', self.dsIsAllowTextShadow)
            AddHandSplitProp(colShadow, 'dsShadowBlur') #Размытие тени разделяет их, чтобы не сливались вместе по середине.
            row = AddHandSplitProp(colShadow, 'dsShadowOffset', isReturnLy=True).row(align=True)
            row.row().prop(self, 'dsShadowOffset', text="X  ", index=0, icon_only=True)
            row.row().prop(self, 'dsShadowOffset', text="Y  ", index=1, icon_only=True)
            colShadow.active = self.dsIsAllowTextShadow
            AddHandSplitProp(colProps, 'dsIsDrawDebug')
        except Exception as ex:
            colMaster.label(text=str(ex), icon='ERROR')
    def DrawTabKeymaps(self, context, where):
        colMaster = where.column()
        try:
            colMaster.separator()
            rowLabelMain = colMaster.row(align=True)
            rowLabel = rowLabelMain.row(align=True)
            rowLabel.alignment = 'CENTER'
            rowLabel.label(icon='DOT')
            rowLabel.label(text=TranslateIface("Node Editor"))
            rowLabelPost = rowLabelMain.row(align=True)
            #rowLabelPost.active = False
            colList = colMaster.column(align=True)
            kmUNe = GetUserKmNe()
            ##
            kmiCats = KmiCats() #todo2 нужно ли переводить названия категорий-групп ниже?
            kmiCats.g = KmiCat('vaKmiMainstreamBoxDiscl', "The Great Trio",   set(), 0, dict_setKmiCats['g']  )
            kmiCats.o = KmiCat('vaKmiOtjersBoxDiscl',     "Others",           set(), 0, dict_setKmiCats['o']   )
            kmiCats.s = KmiCat('vaKmiSpecialBoxDiscl',    "Specials",         set(), 0, dict_setKmiCats['s']   )
            kmiCats.q = KmiCat('vaKmiQqmBoxDiscl',        "Quick quick math", set(), 0, dict_setKmiCats['q'] )
            kmiCats.c = KmiCat('vaKmiCustomBoxDiscl',     "Custom",           set(), 0)
            #В старых версиях аддона с другим методом поиска, на вкладке "keymap" порядок отображался в обратном порядке вызовов регистрации kmidef с одинаковыми `cls`.
            #Теперь сделал так. Как работал предыдущий метод -- для меня загадка.
            scoAll = 0
            for li in kmUNe.keymap_items:
                if li.idname.startswith("node.voronoi_"):
                    #todo3 мб стоит выпендриться, и упаковать всё это через lambda. И переназвать всех на 3 буквы.
                    if li.id<0: #Отрицательный ид для кастомных? Ну ладно. Пусть будет идентифицирующим критерием.
                        kmiCats.c.set_kmis.add(li)
                        kmiCats.c.sco += 1
                    elif [True for pr in {'quickOprFloat','quickOprVector','quickOprBool','quickOprColor','justCallPie','isRepeatLastOperation'} if getattr(li.properties, pr, None)]:
                        kmiCats.q.set_kmis.add(li)
                        kmiCats.q.sco += 1
                    elif li.idname in kmiCats.g.set_idn:
                        kmiCats.g.set_kmis.add(li)
                        kmiCats.g.sco += 1
                    elif li.idname in kmiCats.o.set_idn:
                        kmiCats.o.set_kmis.add(li)
                        kmiCats.o.sco += 1
                    else:
                        kmiCats.s.set_kmis.add(li)
                        kmiCats.s.sco += 1
                    scoAll += 1 #Хоткеев теперь стало тааак много, что неплохо было бы узнать их количество.
            if kmUNe.is_user_modified:
                rowRestore = rowLabelMain.row(align=True)
                rowInfo = rowRestore.row()
                rowInfo.prop(self,'vaInfoRestore', icon='INFO', emboss=False)
                rowInfo.active = False #True, но от постоянного горения рискует мозги прожечь.
                rowRestore.context_pointer_set('keymap', kmUNe)
                rowRestore.operator('preferences.keymap_restore', text=TranslateIface("Restore"))
            else:
                rowLabelMain.label()
            rowAddNew = rowLabelMain.row(align=True)
            rowAddNew.ui_units_x = 12
            rowAddNew.separator()
            rowAddNew.operator(VoronoiAddonTabs.bl_idname, text="Add New", icon='ADD').opt = 'AddNewKmi' # NONE  ADD
            import rna_keymap_ui
            def AddKmisCategory(where, cat):
                if not cat.set_kmis:
                    return
                colListCat = where.row().column(align=True)
                rowDiscl = colListCat.row(align=True)
                rowDiscl.active = False
                tgl = self.AddDisclosureProp(rowDiscl, self, cat.txt_prop, cat.label+f" ({cat.sco})", isWide=True)#, txt_suffIfActive=":")
                if not tgl:
                    return
                for li in sorted(cat.set_kmis, key=lambda a: a.id):
                    colListCat.context_pointer_set('keymap', kmUNe)
                    rna_keymap_ui.draw_kmi([], context.window_manager.keyconfigs.user, kmUNe, li, colListCat, 0) #Заметка: если colListCat будет не colListCat, то возможность удаления kmi станет недоступной.
            AddKmisCategory(colList, kmiCats.c)
            AddKmisCategory(colList, kmiCats.g)
            AddKmisCategory(colList, kmiCats.o)
            AddKmisCategory(colList, kmiCats.s)
            AddKmisCategory(colList, kmiCats.q)
            rowLabelPost.label(text=f"({scoAll})")
        except Exception as ex:
            colMaster.label(text=str(ex), icon='ERROR')
    def draw(self, context):
        colMaster = self.layout.column()
        rowTabs = colMaster.row(align=True)
        #Переключение вкладок через оператор создано, чтобы случайно не сменить вкладку при ведении зажатой мышки, кой есть особый соблазн с таким большим количеством "isColored".
        if True:
            for li in [en for en in self.rna_type.properties['vaUiTabs'].enum_items]:
                rowTabs.row().operator(VoronoiAddonTabs.bl_idname, text=TranslateIface(li.name), depress=self.vaUiTabs==li.identifier).opt = li.identifier
        else:
            rowTabs.prop(self,'vaUiTabs', expand=True)
        match self.vaUiTabs:
            case 'SETTINGS': self.DrawTabSettings(context, colMaster)
            case 'DRAW':     self.DrawTabDraw    (context, colMaster)
            case 'KEYMAP':   self.DrawTabKeymaps (context, colMaster)

list_classes += [VoronoiAddonTabs, VoronoiAddonPrefs]

#todo4 теперь есть пара пар инструментов с одинаковыми по смыслу опциями. Нужно бы это как-то вылизать и/или зашаблонить.

list_helpClasses = []

class TranslationHelper(): #Спасибо пользователю с ником "atticus-lv" за код для переводов на другие языки.
    def __init__(self, data={}, lang=''):
        self.name = voronoiAddonName+lang
        self.translations_dict = dict()
        for src, src_trans in data.items():
            self.translations_dict.setdefault(lang, {})[ ('Operator', src) ] = src_trans
            self.translations_dict.setdefault(lang, {})[ ('*',        src) ] = src_trans
    def register(self):
        try:
            bpy.app.translations.register(self.name, self.translations_dict)
        except:
            try:
                bpy.app.translations.unregister(self.name)
                bpy.app.translations.register(self.name, self.translations_dict)
            except:
                pass
    def unregister(self):
        bpy.app.translations.unregister(self.name)

def RegisterTranslations():
    for di in dict_translations:
        list_helpClasses.append(TranslationHelper( dict_translations[di], di ))
    for li in list_helpClasses:
        li.register()
def UnregisterTranslations():
    for li in list_helpClasses:
        li.unregister()


def GetAddonProp(txt, inx=-1):
    tar = VoronoiAddonPrefs.bl_rna.properties[txt]
    if inx>-1:
        tar = getattr(tar,'enum_items')[inx]
    return tar
def GetAddonPropName(txt, inx=-1):
    return GetAddonProp(txt, inx).name
def GclToolSet(cls):
    return cls.bl_label+voronoiTextToolSettings
def GetAnnotNameFromClass(pcls, txt, kw=0):
    return pcls.__annotations__[txt].keywords['name' if kw==0 else 'description'] #Так вот где они прятались, в аннотациях. А я то уж потерял надежду; думал, вручную придётся.

dict_translations = {}

#todo0 когда настанет день X популярности, нужно будет переделать всю систему перевода VL, чтобы обслужить поток и повысить удобность.
#Что-то вроде словарь{свойство: словарь{язык:перевод, язык:перевод, ..}, ..}.

Gapn = GetAddonPropName
Ganfc = GetAnnotNameFromClass
def CollectTranslationDict(): #Превращено в функцию ради `Gapn()`, который требует регистрации 'VoronoiAddonPrefs'.
    dict_translations['ru_RU'] = { #Последнее обновление для VL 3.6.0
            bl_info['description']:                    "Разнообразные помогалочки для соединения нод, основанные на поле расстояний.",
            "Virtual":                                 "Виртуальный",
            "Restore":                                 "Восстановить",
            "Add New":                                 "Добавить", #Без слова "новый", оно не влезает.
            txt_noMixingOptions:                       "Варианты смешивания отсутствуют",
            txt_copySettAsPyScript:                    "Скопировать настройки аддона как '.py' скрипт",
            GetAddonProp('vaInfoRestore').description: "Этот список лишь копия из настроек. \"Восстановление\" восстановит всё, а не только аддон",
            #Tools:
            GclToolSet(VoronoiLinkerTool):       f"Настройки инструмента {VoronoiLinkerTool.bl_label}:",
            GclToolSet(VoronoiPreviewTool):      f"Настройки инструмента {VoronoiPreviewTool.bl_label}:",
            GclToolSet(VoronoiMixerTool):        f"Настройки инструмента {VoronoiMixerTool.bl_label}:",
            GclToolSet(VoronoiQuickMathTool):    f"Настройки инструмента {VoronoiQuickMathTool.bl_label}:",
            GclToolSet(VoronoiSwapperTool):      f"Настройки инструмента {VoronoiSwapperTool.bl_label}:",
            GclToolSet(VoronoiHiderTool):        f"Настройки инструмента {VoronoiHiderTool.bl_label}:",
            GclToolSet(VoronoiEnumSelectorTool): f"Настройки инструмента {VoronoiEnumSelectorTool.bl_label}:",
            Gapn('vaShowAllToolsOptions'):       "Настройки для всех инструментов:",
            Gapn('vaShowAddonOptions'):          "VL Аддон",
            #Draw:
            "Colored":                    "Цветной",
            Gapn('dsUniformColor'):       "Альтернативный постоянный цвет",
            Gapn('dsNodeColor'):          "Цвет рисования к ноду",
            Gapn('dsSocketAreaAlpha'):    "Прозрачность области сокета",
            Gapn('dsFontFile'):           "Файл шрифта",
            txt_onlyFontFormat:           "Только .ttf или .otf формат",
            Gapn('dsPointOffsetX'):       "Смещение точки по оси X",
            Gapn('dsFrameOffset'):        "Размер рамки",
            Gapn('dsFontSize'):           "Размер шрифта",
            Gapn('dsIsDrawSkArea'):       "Область сокета",
            Gapn('dsDisplayStyle'):       "Стиль отображения рамки",
                Gapn('dsDisplayStyle',0):     "Классический",
                Gapn('dsDisplayStyle',1):     "Упрощённый",
                Gapn('dsDisplayStyle',2):     "Только текст",
            Gapn('dsPointRadius'):        "Размер точки",
            Gapn('dsDistFromCursor'):     "Расстояние до текста от курсора",
            Gapn('dsIsAllowTextShadow'):  "Включить тень текста",
            Gapn('dsShadowCol'):          "Цвет тени",
            Gapn('dsShadowOffset'):       "Смещение тени",
            Gapn('dsShadowBlur'):         "Размытие тени",
            Gapn('dsIsAlwaysLine'):       "Всегда рисовать линию",
            Gapn('dsIsDrawDebug'):        "Отображать отладку",
            #Settings:
            Gapn('vtRepickTrigger'):                "Условие перевыбора",
                Gapn('vtRepickTrigger',0):              "Полное совпадение с вызывающими модификаторами",
                Gapn('vtRepickTrigger',1):              "Хотябы один из модификаторов",
            Gapn('vlReroutesCanInAnyType'):         "Рероуты могут подключаться в любой тип",
            Gapn('vlDeselectAllNodes'):             "Снимать выделение со всех нодов при активации",
            Gapn('vlAnnoyingIgnoring'):             "Надоедливое игнорирование",
            Gapn('vpAllowClassicCompositorViewer'): "Разрешить классический Viewer Композитора",
            Gapn('vpAllowClassicGeoViewer'):        "Разрешить классический Viewer Геометрических узлов",
            Gapn('vpIsLivePreview'):                "Предпросмотр в реальном времени",
            Gapn('vpRvEeIsColorOnionNodes'):        "Луковичные цвета нод",
            Gapn('vpRvEeSksHighlighting'):          "Подсветка топологических соединений",
            Gapn('vpRvEeIsSavePreviewResults'):     "Сохранять результаты предпросмотра",
            Gapn('vmReroutesCanInAnyType'):         "Рероуты могут смешиваться с любым типом",
            Gapn('vmPieType'):                      "Тип пирога",
                Gapn('vmPieType',0):                    "Скорость",
                Gapn('vmPieType',1):                    "Контроль",
            Gapn('vmPieScale'):                     "Размер пирога",
            Gapn('vmPieSocketDisplayType'):         "Отображение типа сокета",
            Gapn('vmPieAlignment'):                 "Выравнивание между элементами",
            Gapn('vhNeverHideGeometry'):            "Никогда не скрывать входные сокеты геометрии",
            Gapn('vhHideBoolSocket'):               "Скрывать Boolean сокеты",
            Gapn('vhHideHiddenBoolSocket'):         "Скрывать скрытые Boolean сокеты",
                Gapn('vhHideBoolSocket',1):             "Если True",
                Gapn('vhHideBoolSocket',3):             "Если False",
            Gapn('vhIsUnhideVirtual'):              "Показывать виртуальные",
            Gapn('vhIsToggleNodesOnDrag'):          "Переключать ноды при ведении курсора",
            Gapn('vhDrawNodeNameLabel'):            "Показывать текст для нода",
                Gapn('vhDrawNodeNameLabel',1):          "Только имя",
                Gapn('vhDrawNodeNameLabel',2):          "Только заголовок",
                Gapn('vhDrawNodeNameLabel',3):          "Имя и заголовок",
            Gapn('vhLabelDispalySide'):             "Сторона отображения заголовка",
            Gapn('vesIsInstantActivation'):         "Моментальная активация",
            Gapn('vesIsDrawEnumNames'):             "Рисовать имена свойств перечисления",
            Gapn('vesBoxScale'):                    "Масштаб панели",
            Gapn('vesDisplayLabels'):               "Отображать имена свойств перечислений",
            Gapn('vesDarkStyle'):                   "Тёмный стиль",
            #Tool settings:
            Ganfc(VoronoiTool,'isPassThrough'):                   "Пропускать через выделение нода",
            Ganfc(VoronoiTool,'isPassThrough',1):                 "Клик над нодом активирует выделение, а не инструмент",
            Ganfc(VoronoiToolDblSk,'isCanBetweenFields'):         "Может между полями",
            Ganfc(VoronoiToolDblSk,'isCanBetweenFields',1):       "Инструменты могут соединяться между различными типами полей",
            Ganfc(VoronoiPreviewTool,'isSelectingPreviewedNode'): "Выделять предпросматриваемый нод",
            Ganfc(VoronoiPreviewTool,'isTriggerOnlyOnLink'):      "Триггериться только на связанные",
            Ganfc(VoronoiPreviewTool,'isEqualAnchorType'):        "Равный тип якоря",
            Ganfc(VoronoiMixerTool,'isCanFromOne'):               "Может от одного сокета",
            Ganfc(VoronoiMixerTool,'isPlaceImmediately'):         "Размещать моментально",
            Ganfc(VoronoiQuickMathTool,'isHideOptions'):          "Скрывать опции нода",
            Ganfc(VoronoiQuickMathTool,'justCallPie'):            "Просто вызвать пирог",
            Ganfc(VoronoiQuickMathTool,'isRepeatLastOperation'):  "Повторить последнюю операцию",
            Ganfc(VoronoiQuickMathTool,'quickOprFloat'):          "Скаляр (быстро)",
            Ganfc(VoronoiQuickMathTool,'quickOprVector'):         "Вектор (быстро)",
            Ganfc(VoronoiQuickMathTool,'quickOprBool'):           "Логический (быстро)",
            Ganfc(VoronoiQuickMathTool,'quickOprColor'):          "Цвет (быстро)",
            Ganfc(VoronoiSwapperTool,'isAddMode'):                "Режим добавления",
            Ganfc(VoronoiSwapperTool,'isIgnoreLinked'):           "Игнорировать связанные сокеты",
            Ganfc(VoronoiSwapperTool,'isCanAnyType'):             "Может меняться с любым типом",
            Ganfc(VoronoiHiderTool,'isHideSocket'):               "Режим сокрытия",
            Ganfc(VoronoiHiderTool,'isTriggerOnCollapsedNodes'):  "Триггериться на свёрнутые ноды",
            Ganfc(VoronoiMassLinkerTool,'isIgnoreExistingLinks'): "Игнорировать существующие связи",
            Ganfc(VoronoiEnumSelectorTool,'isToggleOptions'):     "Режим переключения опций нода",
            Ganfc(VoronoiEnumSelectorTool,'isPieChoice'):         "Выбор пирогом",
            Ganfc(VoronoiEnumSelectorTool,'isSelectNode'):        "Выделять целевой нод",
            Ganfc(VoronoiRepeatingTool,'isAutoRepeatMode'):       "Режим авто-повторения",
            Ganfc(VoronoiRepeatingTool,'isFromOut'):              "Из выхода",
            Ganfc(VoronoiLinksTransferTool,'isByOrder'):          "Переносить по порядку",
            Ganfc(VoronoiInterfaceCopierTool,'isPaste'):          "Вставить",
            Ganfc(VoronoiWarperTool,'isZoomedTo'):                  "Центрировать",
            }
    dict_translations['zh_CN'] = { #VL 3.5.6
            bl_info['description']: "基于距离场的多种节点连接辅助工具。",
            "Virtual": "虚拟",
            "Restore": "恢复",
            "Add New": "添加",
            txt_noMixingOptions:                       "无混合选项",
            txt_copySettAsPyScript:                    "将插件设置复制为'.py'脚本",
            GetAddonProp('vaInfoRestore').description: "此列表只是设置的副本。“恢复”将还原所有设置，而不仅仅是插件。",
            # 工具:
            GclToolSet(VoronoiLinkerTool):       f"{VoronoiLinkerTool.bl_label}工具设置:",
            GclToolSet(VoronoiPreviewTool):      f"{VoronoiPreviewTool.bl_label}工具设置:",
            GclToolSet(VoronoiMixerTool):        f"{VoronoiMixerTool.bl_label}工具设置:",
            GclToolSet(VoronoiQuickMathTool):    f"{VoronoiQuickMathTool.bl_label}工具设置:",
            GclToolSet(VoronoiSwapperTool):      f"{VoronoiSwapperTool.bl_label}工具设置:",
            GclToolSet(VoronoiHiderTool):        f"{VoronoiHiderTool.bl_label}工具设置:",
            GclToolSet(VoronoiEnumSelectorTool): f"{VoronoiEnumSelectorTool.bl_label}工具设置:",
            Gapn('vaShowAllToolsOptions'):       "所有工具的设置:",
            Gapn('vaShowAddonOptions'):          "VL 插件",
            # 绘制:
            "Colored": "有颜色的",
            Gapn('dsUniformColor'):       "替代的统一颜色",
            Gapn('dsNodeColor'):          "节点的绘制颜色",
            Gapn('dsSocketAreaAlpha'):    "端口区域的透明度",
            Gapn('dsFontFile'):           "字体文件",
            txt_onlyFontFormat:           "只支持.ttf或.otf格式",
            Gapn('dsPointOffsetX'):       "X轴上的点偏移",
            Gapn('dsFrameOffset'):        "边框大小",
            Gapn('dsFontSize'):           "字体大小",
            Gapn('dsIsDrawSkArea'):       "端口区域",
            Gapn('dsDisplayStyle'):       "边框显示样式",
                Gapn('dsDisplayStyle',0):     "经典",
                Gapn('dsDisplayStyle',1):     "简化",
                Gapn('dsDisplayStyle',2):     "仅文本",
            Gapn('dsPointRadius'):        "点的大小",
            Gapn('dsDistFromCursor'):     "到文本的距离",
            Gapn('dsIsAllowTextShadow'):  "启用文本阴影",
            Gapn('dsShadowCol'):          "阴影颜色",
            Gapn('dsShadowOffset'):       "阴影偏移",
            Gapn('dsShadowBlur'):         "阴影模糊",
            Gapn('dsIsAlwaysLine'):       "始终绘制线条",
            Gapn('dsIsDrawDebug'):        "显示调试信息",
            # 设置:
            Gapn('vtRepickTrigger'):                "重新选择触发条件",
                Gapn('vtRepickTrigger',0):              "与所有调用修饰符完全匹配",
                Gapn('vtRepickTrigger',1):              "至少一个修饰符匹配",
            Gapn('vlReroutesCanInAnyType'):         "重新路由可以连接到任何类型",
            Gapn('vlDeselectAllNodes'):             "在激活时取消选择所有节点",
#            Gapn('vlAnnoyingIgnoring'):                   "",
            Gapn('vpAllowClassicCompositorViewer'): "允许经典的合成器查看器",
            Gapn('vpAllowClassicGeoViewer'):        "允许经典的几何节点查看器",
            Gapn('vpIsLivePreview'):                "实时预览",
            Gapn('vpRvEeIsColorOnionNodes'):        "颜色节点的显示",
            Gapn('vpRvEeSksHighlighting'):          "拓扑连接的高亮显示",
            Gapn('vpRvEeIsSavePreviewResults'):     "保存预览结果",
            Gapn('vmReroutesCanInAnyType'):         "重新路由可以与任何类型混合",
            Gapn('vmPieType'):                      "饼图类型",
                Gapn('vmPieType',0):                    "速度",
                Gapn('vmPieType',1):                    "控制",
            Gapn('vmPieScale'):                     "饼图大小",
            Gapn('vmPieSocketDisplayType'):         "显示端口类型",
            Gapn('vmPieAlignment'):                 "元素对齐方式",
            Gapn('vhNeverHideGeometry'):            "永不隐藏几何输入端口",
            Gapn('vhHideBoolSocket'):               "隐藏布尔端口",
            Gapn('vhHideHiddenBoolSocket'):         "隐藏隐藏的布尔端口",
                Gapn('vhHideBoolSocket',1):             "如果为True",
                Gapn('vhHideBoolSocket',3):             "如果为False",
            Gapn('vhIsUnhideVirtual'):              "显示虚拟端口",
            Gapn('vhIsToggleNodesOnDrag'):          "拖动时切换节点",
            Gapn('vhDrawNodeNameLabel'):            "显示节点标签",
                Gapn('vhDrawNodeNameLabel',1):          "仅名称",
                Gapn('vhDrawNodeNameLabel',2):          "仅标题",
                Gapn('vhDrawNodeNameLabel',3):          "名称和标题",
            Gapn('vhLabelDispalySide'):             "标签显示位置",
            Gapn('vesIsInstantActivation'):         "即时激活",
            Gapn('vesIsDrawEnumNames'):             "绘制枚举属性名称",
            Gapn('vesBoxScale'):                    "面板比例",
            Gapn('vesDisplayLabels'):               "显示枚举属性名称",
            Gapn('vesDarkStyle'):                   "暗色风格",
            # 工具设置:
            Ganfc(VoronoiTool,'isPassThrough'):                   "通过节点选中",
            Ganfc(VoronoiTool,'isPassThrough',1):                 "单击节点激活选择而不是工具",
            Ganfc(VoronoiToolDblSk,'isCanBetweenFields'):         "可以在字段之间连接",
            Ganfc(VoronoiToolDblSk,'isCanBetweenFields',1):       "工具可以连接不同类型的字段",
            Ganfc(VoronoiPreviewTool,'isSelectingPreviewedNode'): "选择预览节点",
            Ganfc(VoronoiPreviewTool,'isTriggerOnlyOnLink'):      "仅触发连接",
#            Ganfc(VoronoiPreviewTool,'isEqualAnchorType'):        "",
            Ganfc(VoronoiMixerTool,'isCanFromOne'):               "从一个端口连接",
            Ganfc(VoronoiMixerTool,'isPlaceImmediately'):         "立即放置",
            Ganfc(VoronoiQuickMathTool,'isHideOptions'):          "隐藏节点选项",
            Ganfc(VoronoiQuickMathTool,'justCallPie'):            "仅调用饼图",
            Ganfc(VoronoiQuickMathTool,'isRepeatLastOperation'):  "重复上一操作",
            Ganfc(VoronoiQuickMathTool,'quickOprFloat'):          "浮点（快速）",
            Ganfc(VoronoiQuickMathTool,'quickOprVector'):         "矢量（快速）",
            Ganfc(VoronoiQuickMathTool,'quickOprBool'):           "布尔（快速）",
            Ganfc(VoronoiQuickMathTool,'quickOprColor'):          "颜色（快速）",
            Ganfc(VoronoiSwapperTool,'isAddMode'):                "添加模式",
            Ganfc(VoronoiSwapperTool,'isIgnoreLinked'):           "忽略已连接的端口",
            Ganfc(VoronoiSwapperTool,'isCanAnyType'):             "可以与任何类型交换",
            Ganfc(VoronoiHiderTool,'isHideSocket'):               "端口隐藏模式",
            Ganfc(VoronoiHiderTool,'isTriggerOnCollapsedNodes'):  "仅触发已折叠节点",
            Ganfc(VoronoiMassLinkerTool,'isIgnoreExistingLinks'): "忽略现有链接",
            Ganfc(VoronoiEnumSelectorTool,'isToggleOptions'):     "选项切换模式",
            Ganfc(VoronoiEnumSelectorTool,'isPieChoice'):         "饼图选择",
            Ganfc(VoronoiEnumSelectorTool,'isSelectNode'):        "选择目标节点",
            Ganfc(VoronoiRepeatingTool,'isAutoRepeatMode'):       "自动重复模式",
            Ganfc(VoronoiRepeatingTool,'isFromOut'):              "从输出开始",
            Ganfc(VoronoiLinksTransferTool,'isByOrder'):          "按顺序传输",
            Ganfc(VoronoiInterfaceCopierTool,'isPaste'):          "粘贴",
#            Ganfc(VoronoiWarperTool,'isZoomedTo'):                  "",
            }
    dict_translations['zh_HANS'] = dict_translations['zh_CN']
    return
    dict_translations['aa_AA'] = { #Ждёт своего часа. Кто же будет вторым?
            bl_info['description']:                     "",
            "Virtual":                                  "",
            "Restore":                                  "",
            #...
            }

list_addonKeymaps = []

newKeyMapNodeEditor = None

def register():
    for li in list_classes:
        bpy.utils.register_class(li)
    ##
    global newKeyMapNodeEditor
    newKeyMapNodeEditor = bpy.context.window_manager.keyconfigs.addon.keymaps.new(name="Node Editor", space_type='NODE_EDITOR')
    for blId, key, shift, ctrl, alt, dict_props in list_kmiDefs:
        kmi = newKeyMapNodeEditor.keymap_items.new(idname=blId, type=key, value='PRESS', shift=shift, ctrl=ctrl, alt=alt)
        #kmi.active = blId!=VoronoiDummyTool.bl_idname
        list_addonKeymaps.append(kmi)
        if dict_props:
            for di in dict_props:
                setattr(kmi.properties, di, dict_props[di])
    ##
    CollectTranslationDict()
    RegisterTranslations()
def unregister():
    for li in reversed(list_classes):
        bpy.utils.unregister_class(li)
    ##
    global newKeyMapNodeEditor
    for li in list_addonKeymaps:
        newKeyMapNodeEditor.keymap_items.remove(li)
    list_addonKeymaps.clear()
    ##
    UnregisterTranslations()


#Мой гит в bl_info, это конечно же, круто, однако было бы не плохо иметь ещё и явно указанные способы связи:
#  coaltangle@gmail.com
#  ^ Моя почта. Если вдруг случится апокалипсис, или эта VL-археологическая-находка сможет решить не полиномиальную задачу, то писать туда.
# Для более реалтаймового общения (предпочтительно) и по вопросам об аддоне и его коде пишите на мой дискорд 'ugorek#6434'.

def DisableKmis(): #Для повторных запусков скрипта. Работает до первого "Restore".
    kmUNe = GetUserKmNe()
    for li, *oi in list_kmiDefs:
        for kmiCon in kmUNe.keymap_items:
            if li==kmiCon.idname:
                kmiCon.active = False #Это удаляет дубликаты. Хак?
                kmiCon.active = True #Вернуть обратно, если оригинал.
if __name__=="__main__":
    DisableKmis() #Кажется не важно в какой очерёдности вызывать, перед или после добавления хоткеев.
    register()
