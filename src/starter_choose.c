#include "global.h"
#include "bg.h"
#include "data.h"
#include "decompress.h"
#include "event_data.h"
#include "gpu_regs.h"
#include "graphics.h"
#include "international_string_util.h"
#include "main.h"
#include "menu.h"
#include "palette.h"
#include "pokemon.h"
#include "pokemon_icon.h"
#include "pokemon_summary_screen.h"
#include "scanline_effect.h"
#include "sound.h"
#include "sprite.h"
#include "starter_choose.h"
#include "string_util.h"
#include "strings.h"
#include "task.h"
#include "text.h"
#include "text_window.h"
#include "trainer_pokemon_sprites.h"
#include "window.h"
#include "constants/rgb.h"
#include "constants/songs.h"
#include "constants/species.h"

extern const struct TypeInfo gTypesInfo[NUMBER_OF_MON_TYPES];

// Kept for credits, the save-failed screen, and Battle Factory.
const u16 gBirchBagGrass_Pal[] = INCGFX_U16("graphics/starter_choose/tiles.png", ".gbapal");
const u32 gBirchBagTilemap[] = INCGFX_U32("graphics/starter_choose/birch_bag.bin", ".smolTM");
const u32 gBirchGrassTilemap[] = INCGFX_U32("graphics/starter_choose/birch_grass.bin", ".smolTM");
const u32 gBirchBagGrass_Gfx[] = INCGFX_U32("graphics/starter_choose/tiles.png", ".4bpp.smol");
const u32 gPokeballSelection_Gfx[] = INCGFX_U32("graphics/starter_choose/pokeball_selection.png", ".4bpp.smol");

static const u16 sStarterMenu_Pal[] = INCGFX_U16("graphics/starter_choose/menu_tiles.png", ".gbapal");
static const u32 sStarterMenu_Gfx[] = INCGFX_U32("graphics/starter_choose/menu_tiles.png", ".4bpp.smol");
static const u32 sStarterMenu_Tilemap[] = INCGFX_U32("graphics/starter_choose/menu.bin", ".smolTM");
static const u16 sCursor_Pal[] = INCGFX_U16("graphics/starter_choose/cursor.png", ".gbapal");
static const u32 sCursor_Gfx[] = INCGFX_U32("graphics/starter_choose/cursor.png", ".4bpp.smol");

#define TAG_STARTER_CURSOR 0x3100
#define WIN_HEADER 0
#define WIN_FOOTER 1
#define WIN_NAME   2
#define SPRITE_NONE 0xFF

#define tRegion        data[0]
#define tCursor        data[1]
#define tConfirm       data[2]
#define tPicSprite     data[3]
#define tCursorSprite  data[4]
#define tType0         data[5]
#define tType1         data[6]

// Default 10x9 list cloned from Quetzal's starter menu.
// Shuffle this RAM copy later for a randomizer; persist it in the save block when that lands.
static const u16 sDefaultStarterChoices[STARTER_CHOICE_COUNT] =
{
    // Kanto
    SPECIES_BULBASAUR, SPECIES_CHARMANDER, SPECIES_SQUIRTLE,
    SPECIES_PIKACHU,   SPECIES_ZUBAT,      SPECIES_GASTLY,
    SPECIES_DITTO,     SPECIES_EEVEE,      SPECIES_PORYGON,
    // Johto
    SPECIES_CHIKORITA, SPECIES_CYNDAQUIL,  SPECIES_TOTODILE,
    SPECIES_TOGEPI,    SPECIES_SNEASEL,    SPECIES_UNOWN,
    SPECIES_DRATINI,   SPECIES_MAREEP,     SPECIES_SNUBBULL,
    // Hoenn
    SPECIES_TREECKO,   SPECIES_TORCHIC,    SPECIES_MUDKIP,
    SPECIES_RALTS,     SPECIES_AZURILL,    SPECIES_ARON,
    SPECIES_ELECTRIKE, SPECIES_TRAPINCH,   SPECIES_BAGON,
    // Sinnoh
    SPECIES_TURTWIG,   SPECIES_CHIMCHAR,   SPECIES_PIPLUP,
    SPECIES_BUIZEL,    SPECIES_HAPPINY,    SPECIES_SHINX,
    SPECIES_GIBLE,     SPECIES_SNOVER,     SPECIES_ROTOM,
    // Unova
    SPECIES_SNIVY,     SPECIES_TEPIG,      SPECIES_OSHAWOTT,
    SPECIES_AXEW,      SPECIES_TYMPOLE,    SPECIES_ZORUA,
    SPECIES_TYNAMO,    SPECIES_SOLOSIS,    SPECIES_PAWNIARD,
    // Kalos
    SPECIES_CHESPIN,   SPECIES_FENNEKIN,   SPECIES_FROAKIE,
    SPECIES_FLABEBE,   SPECIES_HELIOPTILE, SPECIES_ESPURR,
    SPECIES_HONEDGE,   SPECIES_SKIDDO,     SPECIES_SYLVEON,
    // Alola
    SPECIES_ROWLET,    SPECIES_LITTEN,     SPECIES_POPPLIO,
    SPECIES_ROCKRUFF,  SPECIES_COSMOG,     SPECIES_BOUNSWEET,
    SPECIES_MAREANIE,  SPECIES_PICHU,      SPECIES_MIMIKYU,
    // Galar
    SPECIES_GROOKEY,   SPECIES_SCORBUNNY,  SPECIES_SOBBLE,
    SPECIES_IMPIDIMP,  SPECIES_ARROKUDA,   SPECIES_HATENNA,
    SPECIES_FALINKS,   SPECIES_MORPEKO,    SPECIES_DREEPY,
    // Paldea
    SPECIES_SPRIGATITO, SPECIES_FUECOCO,   SPECIES_QUAXLY,
    SPECIES_PAWMI,      SPECIES_CHARCADET, SPECIES_TINKATINK,
    SPECIES_FINIZEN,    SPECIES_FRIGIBAX,  SPECIES_CERULEDGE,
    // Hisui (page 10 was off-screen in the clip)
    SPECIES_ROWLET,           SPECIES_CYNDAQUIL,       SPECIES_OSHAWOTT,
    SPECIES_GROWLITHE_HISUI,  SPECIES_VOLTORB_HISUI,   SPECIES_QWILFISH_HISUI,
    SPECIES_SNEASEL_HISUI,    SPECIES_ZORUA_HISUI,     SPECIES_GOOMY,
};

static const u8 sText_ChooseStarter[] = _("CHOOSE A STARTER");
static const u8 sText_RegionKanto[] = _("{LEFT_ARROW} KANTO 1/10 {RIGHT_ARROW}");
static const u8 sText_RegionJohto[] = _("{LEFT_ARROW} JOHTO 2/10 {RIGHT_ARROW}");
static const u8 sText_RegionHoenn[] = _("{LEFT_ARROW} HOENN 3/10 {RIGHT_ARROW}");
static const u8 sText_RegionSinnoh[] = _("{LEFT_ARROW} SINNOH 4/10 {RIGHT_ARROW}");
static const u8 sText_RegionUnova[] = _("{LEFT_ARROW} UNOVA 5/10 {RIGHT_ARROW}");
static const u8 sText_RegionKalos[] = _("{LEFT_ARROW} KALOS 6/10 {RIGHT_ARROW}");
static const u8 sText_RegionAlola[] = _("{LEFT_ARROW} ALOLA 7/10 {RIGHT_ARROW}");
static const u8 sText_RegionGalar[] = _("{LEFT_ARROW} GALAR 8/10 {RIGHT_ARROW}");
static const u8 sText_RegionPaldea[] = _("{LEFT_ARROW} PALDEA 9/10 {RIGHT_ARROW}");
static const u8 sText_RegionHisui[] = _("{LEFT_ARROW} HISUI 10/10 {RIGHT_ARROW}");
static const u8 *const sRegionLabels[STARTER_REGION_COUNT] =
{
    sText_RegionKanto,
    sText_RegionJohto,
    sText_RegionHoenn,
    sText_RegionSinnoh,
    sText_RegionUnova,
    sText_RegionKalos,
    sText_RegionAlola,
    sText_RegionGalar,
    sText_RegionPaldea,
    sText_RegionHisui,
};
static const u8 sText_FooterBrowse[] = _("{L_BUTTON}{R_BUTTON} REGION     {A_BUTTON} CHOOSE");
static const u8 sText_FooterConfirm[] = _("{A_BUTTON} CONFIRM     {B_BUTTON} BACK");

static const u8 sHeaderTextColors[] = {TEXT_COLOR_TRANSPARENT, TEXT_COLOR_WHITE, TEXT_COLOR_DARK_GRAY};
static const u8 sNameTextColors[] = {TEXT_COLOR_TRANSPARENT, TEXT_COLOR_WHITE, TEXT_COLOR_DARK_GRAY};

// Must match tools/gen_starter_menu_gfx.py
static const u8 sGridCoords[STARTER_SLOTS_PER_REGION][2] =
{
    {32, 48}, {72, 48}, {112, 48},
    {32, 84}, {72, 84}, {112, 84},
    {32, 120}, {72, 120}, {112, 120},
};

#define PIC_X 184
#define PIC_Y 64
#define TYPE_ICON_Y 128
#define TYPE_ICON_X0 168
#define TYPE_ICON_X1 204

static const u16 sTypeBgColors[NUMBER_OF_MON_TYPES][2] =
{
    [TYPE_NONE]     = {RGB2GBA(200, 200, 200), RGB2GBA(176, 176, 176)},
    [TYPE_NORMAL]   = {RGB2GBA(216, 212, 192), RGB2GBA(192, 188, 168)},
    [TYPE_FIGHTING] = {RGB2GBA(216, 152, 136), RGB2GBA(192, 128, 112)},
    [TYPE_FLYING]   = {RGB2GBA(176, 200, 232), RGB2GBA(152, 176, 208)},
    [TYPE_POISON]   = {RGB2GBA(192, 152, 216), RGB2GBA(168, 128, 192)},
    [TYPE_GROUND]   = {RGB2GBA(220, 196, 144), RGB2GBA(196, 172, 120)},
    [TYPE_ROCK]     = {RGB2GBA(196, 180, 128), RGB2GBA(172, 156, 104)},
    [TYPE_BUG]      = {RGB2GBA(188, 208, 112), RGB2GBA(164, 184, 88)},
    [TYPE_GHOST]    = {RGB2GBA(168, 144, 200), RGB2GBA(144, 120, 176)},
    [TYPE_STEEL]    = {RGB2GBA(192, 200, 208), RGB2GBA(168, 176, 184)},
    [TYPE_MYSTERY]  = {RGB2GBA(200, 200, 200), RGB2GBA(176, 176, 176)},
    [TYPE_FIRE]     = {RGB2GBA(232, 168, 112), RGB2GBA(208, 144, 88)},
    [TYPE_WATER]    = {RGB2GBA(144, 184, 232), RGB2GBA(120, 160, 208)},
    [TYPE_GRASS]    = {RGB2GBA(168, 212, 140), RGB2GBA(144, 188, 116)},
    [TYPE_ELECTRIC] = {RGB2GBA(236, 220, 112), RGB2GBA(212, 196, 88)},
    [TYPE_PSYCHIC]  = {RGB2GBA(232, 152, 176), RGB2GBA(208, 128, 152)},
    [TYPE_ICE]      = {RGB2GBA(168, 224, 224), RGB2GBA(144, 200, 200)},
    [TYPE_DRAGON]   = {RGB2GBA(136, 144, 216), RGB2GBA(112, 120, 192)},
    [TYPE_DARK]     = {RGB2GBA(152, 136, 128), RGB2GBA(128, 112, 104)},
    [TYPE_FAIRY]    = {RGB2GBA(232, 176, 200), RGB2GBA(208, 152, 176)},
    [TYPE_STELLAR]  = {RGB2GBA(200, 208, 232), RGB2GBA(176, 184, 208)},
};

static const struct BgTemplate sBgTemplates[] =
{
    {
        .bg = 0,
        .charBaseIndex = 2,
        .mapBaseIndex = 31,
        .screenSize = 0,
        .paletteMode = 0,
        .priority = 0,
        .baseTile = 0
    },
    {
        .bg = 2,
        .charBaseIndex = 0,
        .mapBaseIndex = 6,
        .screenSize = 0,
        .paletteMode = 0,
        .priority = 2,
        .baseTile = 0
    },
};

static const struct WindowTemplate sWindowTemplates[] =
{
    { // header
        .bg = 0,
        .tilemapLeft = 3,
        .tilemapTop = 0,
        .width = 27,
        .height = 2,
        .paletteNum = 15,
        .baseBlock = 1
    },
    { // footer
        .bg = 0,
        .tilemapLeft = 1,
        .tilemapTop = 18,
        .width = 28,
        .height = 2,
        .paletteNum = 15,
        .baseBlock = 55
    },
    { // name
        .bg = 0,
        .tilemapLeft = 18,
        .tilemapTop = 13,
        .width = 11,
        .height = 2,
        .paletteNum = 15,
        .baseBlock = 111
    },
    DUMMY_WIN_TEMPLATE,
};

static const struct CompressedSpriteSheet sCursorSpriteSheet =
{
    .data = sCursor_Gfx,
    .size = 0x200,
    .tag = TAG_STARTER_CURSOR
};

static const struct SpritePalette sCursorSpritePalette =
{
    .data = sCursor_Pal,
    .tag = TAG_STARTER_CURSOR
};

static const struct OamData sOam_Cursor =
{
    .y = 0,
    .affineMode = ST_OAM_AFFINE_OFF,
    .objMode = ST_OAM_OBJ_NORMAL,
    .mosaic = FALSE,
    .bpp = ST_OAM_4BPP,
    .shape = SPRITE_SHAPE(32x32),
    .x = 0,
    .matrixNum = 0,
    .size = SPRITE_SIZE(32x32),
    .tileNum = 0,
    .priority = 0,
    .paletteNum = 0,
    .affineParam = 0,
};

static const union AnimCmd sAnim_Cursor[] =
{
    ANIMCMD_FRAME(0, 0),
    ANIMCMD_END,
};

static const union AnimCmd *const sAnims_Cursor[] = { sAnim_Cursor };

static const struct SpriteTemplate sSpriteTemplate_Cursor =
{
    .tileTag = TAG_STARTER_CURSOR,
    .paletteTag = TAG_STARTER_CURSOR,
    .oam = &sOam_Cursor,
    .anims = sAnims_Cursor,
    .images = NULL,
    .affineAnims = gDummySpriteAffineAnimTable,
    .callback = SpriteCallbackDummy,
};

static EWRAM_DATA u16 sStarterChoices[STARTER_CHOICE_COUNT] = {0};
static EWRAM_DATA bool8 sStarterChoicesInitialized = FALSE;
static EWRAM_DATA u8 sIconSprites[STARTER_SLOTS_PER_REGION] = {0};

static void CB2_StarterChoose(void);
static void VblankCB_StarterChoose(void);
static void Task_HandleStarterInput(u8 taskId);
static void InitStarterChooseGfx(void);
static void CreateStarterChooseSprites(u8 taskId);
static void RefreshRegionIcons(u8 taskId);
static void RefreshSelection(u8 taskId);
static void SetTypeBackground(enum Type type);
static void PrintHeader(u8 region);
static void PrintFooter(bool32 confirm);
static void PrintSpeciesName(enum Species species);
static void UpdateTypeIcons(u8 taskId, enum Species species);
static void DestroyIconSprites(void);
static void ExitStarterChoose(u8 taskId, u16 choice);
static u16 GetChoiceIndex(u8 region, u8 cursor);
static enum Species GetChoiceSpecies(u8 region, u8 cursor);
static s32 StepCursor(u8 region, s32 cursor, s32 delta);

void InitStarterChoices(void)
{
    memcpy(sStarterChoices, sDefaultStarterChoices, sizeof(sStarterChoices));
    sStarterChoicesInitialized = TRUE;
}

u16 *GetStarterChoiceList(void)
{
    if (!sStarterChoicesInitialized)
        InitStarterChoices();
    return sStarterChoices;
}

u16 GetStarterPokemon(u16 chosenStarterId)
{
    if (!sStarterChoicesInitialized)
        InitStarterChoices();
    if (chosenStarterId >= STARTER_CHOICE_COUNT)
        chosenStarterId = 0;
    return sStarterChoices[chosenStarterId];
}

void BufferStarterTypeExample(void)
{
    enum Species species = GetStarterPokemon(VarGet(VAR_STARTER_MON));
    StringCopy(gStringVar1, GetSpeciesName(species));
    StringCopy(gStringVar2, gTypesInfo[GetSpeciesType(species, 0)].name);
}

void CB2_ChooseStarter(void)
{
    u8 taskId;

    SetVBlankCallback(NULL);
    SetGpuReg(REG_OFFSET_DISPCNT, 0);
    SetGpuReg(REG_OFFSET_BG3CNT, 0);
    SetGpuReg(REG_OFFSET_BG2CNT, 0);
    SetGpuReg(REG_OFFSET_BG1CNT, 0);
    SetGpuReg(REG_OFFSET_BG0CNT, 0);

    ChangeBgX(0, 0, BG_COORD_SET);
    ChangeBgY(0, 0, BG_COORD_SET);
    ChangeBgX(2, 0, BG_COORD_SET);
    ChangeBgY(2, 0, BG_COORD_SET);

    DmaFill16(3, 0, VRAM, VRAM_SIZE);
    DmaFill32(3, 0, OAM, OAM_SIZE);
    DmaFill16(3, 0, PLTT, PLTT_SIZE);

    ResetBgsAndClearDma3BusyFlags(0);
    InitBgsFromTemplates(0, sBgTemplates, ARRAY_COUNT(sBgTemplates));
    InitWindows(sWindowTemplates);
    DeactivateAllTextPrinters();
    ClearScheduledBgCopiesToVram();
    ScanlineEffect_Stop();
    ResetTasks();
    ResetSpriteData();
    ResetPaletteFade();
    FreeAllSpritePalettes();
    ResetAllPicSprites();

    InitStarterChooseGfx();
    BeginNormalPaletteFade(PALETTES_ALL, 0, 0x10, 0, RGB_BLACK);

    EnableInterrupts(DISPSTAT_VBLANK);
    SetVBlankCallback(VblankCB_StarterChoose);
    SetMainCallback2(CB2_StarterChoose);

    SetGpuReg(REG_OFFSET_WININ, 0);
    SetGpuReg(REG_OFFSET_WINOUT, 0);
    SetGpuReg(REG_OFFSET_BLDCNT, 0);
    SetGpuReg(REG_OFFSET_DISPCNT, DISPCNT_OBJ_ON | DISPCNT_OBJ_1D_MAP);
    ShowBg(0);
    ShowBg(2);

    if (!sStarterChoicesInitialized)
        InitStarterChoices();

    taskId = CreateTask(Task_HandleStarterInput, 0);
    gTasks[taskId].tRegion = 0;
    gTasks[taskId].tCursor = 0;
    gTasks[taskId].tConfirm = FALSE;
    gTasks[taskId].tPicSprite = SPRITE_NONE;
    gTasks[taskId].tType0 = SPRITE_NONE;
    gTasks[taskId].tType1 = SPRITE_NONE;
    CreateStarterChooseSprites(taskId);
    RefreshRegionIcons(taskId);
    RefreshSelection(taskId);
}

static void CB2_StarterChoose(void)
{
    RunTasks();
    AnimateSprites();
    BuildOamBuffer();
    DoScheduledBgTilemapCopiesToVram();
    UpdatePaletteFade();
}

static void VblankCB_StarterChoose(void)
{
    LoadOam();
    ProcessSpriteCopyRequests();
    TransferPlttBuffer();
}

static void InitStarterChooseGfx(void)
{
    DecompressDataWithHeaderVram(sStarterMenu_Gfx, (void *)VRAM);
    DecompressDataWithHeaderVram(sStarterMenu_Tilemap, (void *)(BG_SCREEN_ADDR(6)));
    LoadPalette(sStarterMenu_Pal, BG_PLTT_ID(0), sizeof(sStarterMenu_Pal));
    LoadPalette(GetOverworldTextboxPalettePtr(), BG_PLTT_ID(15), PLTT_SIZE_4BPP);
    LoadMonIconPalettes();
    LoadCompressedSpriteSheet(&sCursorSpriteSheet);
    LoadSpritePalette(&sCursorSpritePalette);
    LoadCompressedSpriteSheet(&gSpriteSheet_MoveTypes);
    LoadPalette(gMoveTypes_Pal, OBJ_PLTT_ID(13), 3 * PLTT_SIZE_4BPP);
}

static void CreateStarterChooseSprites(u8 taskId)
{
    u8 i;
    u8 spriteId;

    for (i = 0; i < STARTER_SLOTS_PER_REGION; i++)
        sIconSprites[i] = SPRITE_NONE;

    spriteId = CreateSprite(&sSpriteTemplate_Cursor, sGridCoords[0][0], sGridCoords[0][1], 0);
    gTasks[taskId].tCursorSprite = spriteId;

    spriteId = CreateSprite(&gSpriteTemplate_MoveTypes, TYPE_ICON_X0, TYPE_ICON_Y, 1);
    gSprites[spriteId].callback = SpriteCallbackDummy;
    gTasks[taskId].tType0 = spriteId;

    spriteId = CreateSprite(&gSpriteTemplate_MoveTypes, TYPE_ICON_X1, TYPE_ICON_Y, 1);
    gSprites[spriteId].callback = SpriteCallbackDummy;
    gTasks[taskId].tType1 = spriteId;
}

static void DestroyIconSprites(void)
{
    u8 i;

    for (i = 0; i < STARTER_SLOTS_PER_REGION; i++)
    {
        if (sIconSprites[i] != SPRITE_NONE)
        {
            FreeAndDestroyMonIconSprite(&gSprites[sIconSprites[i]]);
            sIconSprites[i] = SPRITE_NONE;
        }
    }
}

static u16 GetChoiceIndex(u8 region, u8 cursor)
{
    return region * STARTER_SLOTS_PER_REGION + cursor;
}

static enum Species GetChoiceSpecies(u8 region, u8 cursor)
{
    return GetStarterPokemon(GetChoiceIndex(region, cursor));
}

static s32 StepCursor(u8 region, s32 cursor, s32 delta)
{
    s32 i;

    for (i = 0; i < STARTER_SLOTS_PER_REGION; i++)
    {
        cursor += delta;
        if (cursor < 0)
            cursor = STARTER_SLOTS_PER_REGION - 1;
        else if (cursor >= STARTER_SLOTS_PER_REGION)
            cursor = 0;
        if (GetChoiceSpecies(region, cursor) != SPECIES_NONE)
            return cursor;
    }
    return 0;
}

static void RefreshRegionIcons(u8 taskId)
{
    u8 i;
    u8 region = gTasks[taskId].tRegion;
    enum Species species;

    DestroyIconSprites();
    for (i = 0; i < STARTER_SLOTS_PER_REGION; i++)
    {
        species = GetChoiceSpecies(region, i);
        if (species == SPECIES_NONE)
            continue;
        LoadMonIconPalette(species);
        sIconSprites[i] = CreateMonIcon(species, SpriteCallbackDummy, sGridCoords[i][0], sGridCoords[i][1], 2, 0);
        if (sIconSprites[i] < MAX_SPRITES)
            gSprites[sIconSprites[i]].oam.priority = 1;
        else
            sIconSprites[i] = SPRITE_NONE;
    }
}

static void SetTypeBackground(enum Type type)
{
    u16 fill, watermark;

    if (type >= NUMBER_OF_MON_TYPES)
        type = TYPE_NORMAL;
    fill = sTypeBgColors[type][0];
    watermark = sTypeBgColors[type][1];
    gPlttBufferUnfaded[BG_PLTT_ID(0) + 1] = fill;
    gPlttBufferFaded[BG_PLTT_ID(0) + 1] = fill;
    gPlttBufferUnfaded[BG_PLTT_ID(0) + 2] = watermark;
    gPlttBufferFaded[BG_PLTT_ID(0) + 2] = watermark;
}

static void PrintHeader(u8 region)
{
    const u8 *label = sRegionLabels[region];
    s32 width = GetStringWidth(FONT_NORMAL, label, 0);

    FillWindowPixelBuffer(WIN_HEADER, PIXEL_FILL(0));
    AddTextPrinterParameterized3(WIN_HEADER, FONT_NORMAL, 0, 1, sHeaderTextColors, 0, sText_ChooseStarter);
    AddTextPrinterParameterized3(WIN_HEADER, FONT_NARROW, 216 - width, 1, sHeaderTextColors, 0, label);
    PutWindowTilemap(WIN_HEADER);
    CopyWindowToVram(WIN_HEADER, COPYWIN_FULL);
}

static void PrintFooter(bool32 confirm)
{
    const u8 *text = confirm ? sText_FooterConfirm : sText_FooterBrowse;
    s32 x = GetStringCenterAlignXOffset(FONT_NORMAL, text, 224);

    FillWindowPixelBuffer(WIN_FOOTER, PIXEL_FILL(0));
    AddTextPrinterParameterized3(WIN_FOOTER, FONT_NORMAL, x, 1, sHeaderTextColors, 0, text);
    PutWindowTilemap(WIN_FOOTER);
    CopyWindowToVram(WIN_FOOTER, COPYWIN_FULL);
}

static void PrintSpeciesName(enum Species species)
{
    const u8 *name = GetSpeciesName(species);
    s32 x = GetStringCenterAlignXOffset(FONT_NORMAL, name, 88);

    FillWindowPixelBuffer(WIN_NAME, PIXEL_FILL(0));
    AddTextPrinterParameterized3(WIN_NAME, FONT_NORMAL, x, 1, sNameTextColors, 0, name);
    PutWindowTilemap(WIN_NAME);
    CopyWindowToVram(WIN_NAME, COPYWIN_FULL);
}

static void UpdateTypeIcons(u8 taskId, enum Species species)
{
    enum Type type1 = GetSpeciesType(species, 0);
    enum Type type2 = GetSpeciesType(species, 1);
    u8 sprite0 = gTasks[taskId].tType0;
    u8 sprite1 = gTasks[taskId].tType1;

    StartSpriteAnim(&gSprites[sprite0], type1);
    gSprites[sprite0].oam.paletteNum = gTypesInfo[type1].palette;
    gSprites[sprite0].invisible = FALSE;

    if (type2 == type1 || type2 == TYPE_NONE)
    {
        gSprites[sprite1].invisible = TRUE;
        gSprites[sprite0].x = (TYPE_ICON_X0 + TYPE_ICON_X1) / 2;
    }
    else
    {
        StartSpriteAnim(&gSprites[sprite1], type2);
        gSprites[sprite1].oam.paletteNum = gTypesInfo[type2].palette;
        gSprites[sprite1].invisible = FALSE;
        gSprites[sprite0].x = TYPE_ICON_X0;
        gSprites[sprite1].x = TYPE_ICON_X1;
    }
}

static void RefreshSelection(u8 taskId)
{
    u8 region = gTasks[taskId].tRegion;
    u8 cursor = gTasks[taskId].tCursor;
    enum Species species = GetChoiceSpecies(region, cursor);
    u8 picSprite = gTasks[taskId].tPicSprite;
    u8 cursorSprite = gTasks[taskId].tCursorSprite;

    if (species == SPECIES_NONE)
    {
        cursor = StepCursor(region, cursor, 1);
        gTasks[taskId].tCursor = cursor;
        species = GetChoiceSpecies(region, cursor);
    }

    gSprites[cursorSprite].x = sGridCoords[cursor][0];
    gSprites[cursorSprite].y = sGridCoords[cursor][1];

    if (picSprite != SPRITE_NONE)
    {
        FreeAndDestroyMonPicSprite(picSprite);
        gTasks[taskId].tPicSprite = SPRITE_NONE;
    }

    // 0 is female and loads anim_frontf.png. 0xFF keeps the base front sheet (anim_front.png).
    picSprite = CreateMonPicSprite(species, FALSE, 0xFF, TRUE, PIC_X, PIC_Y, 10, TAG_NONE);
    gSprites[picSprite].oam.priority = 1;
    gTasks[taskId].tPicSprite = picSprite;

    PrintHeader(region);
    PrintFooter(gTasks[taskId].tConfirm);
    PrintSpeciesName(species);
    UpdateTypeIcons(taskId, species);
    SetTypeBackground(GetSpeciesType(species, 0));
}

static void ExitStarterChoose(u8 taskId, u16 choice)
{
    DestroyIconSprites();
    if (gTasks[taskId].tPicSprite != SPRITE_NONE)
        FreeAndDestroyMonPicSprite(gTasks[taskId].tPicSprite);
    if (gTasks[taskId].tCursorSprite != SPRITE_NONE)
        DestroySprite(&gSprites[gTasks[taskId].tCursorSprite]);
    if (gTasks[taskId].tType0 != SPRITE_NONE)
        DestroySprite(&gSprites[gTasks[taskId].tType0]);
    if (gTasks[taskId].tType1 != SPRITE_NONE)
        DestroySprite(&gSprites[gTasks[taskId].tType1]);
    FreeMonIconPalettes();
    ResetAllPicSprites();
    FreeAllWindowBuffers();
    gSpecialVar_Result = choice;
    SetMainCallback2(gMain.savedCallback);
}

static void Task_HandleStarterInput(u8 taskId)
{
    u8 region = gTasks[taskId].tRegion;
    u8 cursor = gTasks[taskId].tCursor;
    s32 next;

    if (gPaletteFade.active)
        return;

    if (gTasks[taskId].tConfirm)
    {
        if (JOY_NEW(A_BUTTON))
        {
            PlaySE(SE_SELECT);
            ExitStarterChoose(taskId, GetChoiceIndex(region, cursor));
        }
        else if (JOY_NEW(B_BUTTON))
        {
            PlaySE(SE_SELECT);
            gTasks[taskId].tConfirm = FALSE;
            PrintFooter(FALSE);
        }
        return;
    }

    if (JOY_NEW(A_BUTTON))
    {
        PlaySE(SE_SELECT);
        PlayCry_Normal(GetChoiceSpecies(region, cursor), 0);
        gTasks[taskId].tConfirm = TRUE;
        PrintFooter(TRUE);
        return;
    }

    if (JOY_NEW(L_BUTTON))
    {
        PlaySE(SE_SELECT);
        gTasks[taskId].tRegion = (region + STARTER_REGION_COUNT - 1) % STARTER_REGION_COUNT;
        RefreshRegionIcons(taskId);
        RefreshSelection(taskId);
        return;
    }
    if (JOY_NEW(R_BUTTON))
    {
        PlaySE(SE_SELECT);
        gTasks[taskId].tRegion = (region + 1) % STARTER_REGION_COUNT;
        RefreshRegionIcons(taskId);
        RefreshSelection(taskId);
        return;
    }

    if (JOY_NEW(DPAD_LEFT))
    {
        next = StepCursor(region, cursor, -1);
        if (next != cursor)
        {
            PlaySE(SE_SELECT);
            gTasks[taskId].tCursor = next;
            RefreshSelection(taskId);
        }
    }
    else if (JOY_NEW(DPAD_RIGHT))
    {
        next = StepCursor(region, cursor, 1);
        if (next != cursor)
        {
            PlaySE(SE_SELECT);
            gTasks[taskId].tCursor = next;
            RefreshSelection(taskId);
        }
    }
    else if (JOY_NEW(DPAD_UP))
    {
        next = cursor - 3;
        if (next < 0)
            next += STARTER_SLOTS_PER_REGION;
        if (GetChoiceSpecies(region, next) == SPECIES_NONE)
            next = StepCursor(region, next, -1);
        if (next != cursor)
        {
            PlaySE(SE_SELECT);
            gTasks[taskId].tCursor = next;
            RefreshSelection(taskId);
        }
    }
    else if (JOY_NEW(DPAD_DOWN))
    {
        next = cursor + 3;
        if (next >= STARTER_SLOTS_PER_REGION)
            next -= STARTER_SLOTS_PER_REGION;
        if (GetChoiceSpecies(region, next) == SPECIES_NONE)
            next = StepCursor(region, next, 1);
        if (next != cursor)
        {
            PlaySE(SE_SELECT);
            gTasks[taskId].tCursor = next;
            RefreshSelection(taskId);
        }
    }
}
