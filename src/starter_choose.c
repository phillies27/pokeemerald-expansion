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
static const u16 sPokeball_Pal[] = INCGFX_U16("graphics/starter_choose/pokeball.png", ".gbapal");
static const u32 sPokeball_Gfx[] = INCGFX_U32("graphics/starter_choose/pokeball.png", ".4bpp.smol");

static const u32 sTypeBgGfx_None[]     = INCGFX_U32("graphics/starter_choose/type_bg/none.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Normal[]   = INCGFX_U32("graphics/starter_choose/type_bg/normal.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Fight[]    = INCGFX_U32("graphics/starter_choose/type_bg/fight.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Flying[]   = INCGFX_U32("graphics/starter_choose/type_bg/flying.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Poison[]   = INCGFX_U32("graphics/starter_choose/type_bg/poison.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Ground[]   = INCGFX_U32("graphics/starter_choose/type_bg/ground.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Rock[]     = INCGFX_U32("graphics/starter_choose/type_bg/rock.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Bug[]      = INCGFX_U32("graphics/starter_choose/type_bg/bug.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Ghost[]    = INCGFX_U32("graphics/starter_choose/type_bg/ghost.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Steel[]    = INCGFX_U32("graphics/starter_choose/type_bg/steel.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Mystery[]  = INCGFX_U32("graphics/starter_choose/type_bg/mystery.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Fire[]     = INCGFX_U32("graphics/starter_choose/type_bg/fire.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Water[]    = INCGFX_U32("graphics/starter_choose/type_bg/water.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Grass[]    = INCGFX_U32("graphics/starter_choose/type_bg/grass.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Electric[] = INCGFX_U32("graphics/starter_choose/type_bg/electric.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Psychic[]  = INCGFX_U32("graphics/starter_choose/type_bg/psychic.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Ice[]      = INCGFX_U32("graphics/starter_choose/type_bg/ice.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Dragon[]   = INCGFX_U32("graphics/starter_choose/type_bg/dragon.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Dark[]     = INCGFX_U32("graphics/starter_choose/type_bg/dark.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Fairy[]    = INCGFX_U32("graphics/starter_choose/type_bg/fairy.png", ".4bpp.smol");
static const u32 sTypeBgGfx_Stellar[]  = INCGFX_U32("graphics/starter_choose/type_bg/stellar.png", ".4bpp.smol");

static const u16 sTypeBgPal_None[]     = INCGFX_U16("graphics/starter_choose/type_bg/none.png", ".gbapal");
static const u16 sTypeBgPal_Normal[]   = INCGFX_U16("graphics/starter_choose/type_bg/normal.png", ".gbapal");
static const u16 sTypeBgPal_Fight[]    = INCGFX_U16("graphics/starter_choose/type_bg/fight.png", ".gbapal");
static const u16 sTypeBgPal_Flying[]   = INCGFX_U16("graphics/starter_choose/type_bg/flying.png", ".gbapal");
static const u16 sTypeBgPal_Poison[]   = INCGFX_U16("graphics/starter_choose/type_bg/poison.png", ".gbapal");
static const u16 sTypeBgPal_Ground[]   = INCGFX_U16("graphics/starter_choose/type_bg/ground.png", ".gbapal");
static const u16 sTypeBgPal_Rock[]     = INCGFX_U16("graphics/starter_choose/type_bg/rock.png", ".gbapal");
static const u16 sTypeBgPal_Bug[]      = INCGFX_U16("graphics/starter_choose/type_bg/bug.png", ".gbapal");
static const u16 sTypeBgPal_Ghost[]    = INCGFX_U16("graphics/starter_choose/type_bg/ghost.png", ".gbapal");
static const u16 sTypeBgPal_Steel[]    = INCGFX_U16("graphics/starter_choose/type_bg/steel.png", ".gbapal");
static const u16 sTypeBgPal_Mystery[]  = INCGFX_U16("graphics/starter_choose/type_bg/mystery.png", ".gbapal");
static const u16 sTypeBgPal_Fire[]     = INCGFX_U16("graphics/starter_choose/type_bg/fire.png", ".gbapal");
static const u16 sTypeBgPal_Water[]    = INCGFX_U16("graphics/starter_choose/type_bg/water.png", ".gbapal");
static const u16 sTypeBgPal_Grass[]    = INCGFX_U16("graphics/starter_choose/type_bg/grass.png", ".gbapal");
static const u16 sTypeBgPal_Electric[] = INCGFX_U16("graphics/starter_choose/type_bg/electric.png", ".gbapal");
static const u16 sTypeBgPal_Psychic[]  = INCGFX_U16("graphics/starter_choose/type_bg/psychic.png", ".gbapal");
static const u16 sTypeBgPal_Ice[]      = INCGFX_U16("graphics/starter_choose/type_bg/ice.png", ".gbapal");
static const u16 sTypeBgPal_Dragon[]   = INCGFX_U16("graphics/starter_choose/type_bg/dragon.png", ".gbapal");
static const u16 sTypeBgPal_Dark[]     = INCGFX_U16("graphics/starter_choose/type_bg/dark.png", ".gbapal");
static const u16 sTypeBgPal_Fairy[]    = INCGFX_U16("graphics/starter_choose/type_bg/fairy.png", ".gbapal");
static const u16 sTypeBgPal_Stellar[]  = INCGFX_U16("graphics/starter_choose/type_bg/stellar.png", ".gbapal");

static const u32 *const sTypeBgGfx[NUMBER_OF_MON_TYPES] =
{
    [TYPE_NONE]     = sTypeBgGfx_None,
    [TYPE_NORMAL]   = sTypeBgGfx_Normal,
    [TYPE_FIGHTING] = sTypeBgGfx_Fight,
    [TYPE_FLYING]   = sTypeBgGfx_Flying,
    [TYPE_POISON]   = sTypeBgGfx_Poison,
    [TYPE_GROUND]   = sTypeBgGfx_Ground,
    [TYPE_ROCK]     = sTypeBgGfx_Rock,
    [TYPE_BUG]      = sTypeBgGfx_Bug,
    [TYPE_GHOST]    = sTypeBgGfx_Ghost,
    [TYPE_STEEL]    = sTypeBgGfx_Steel,
    [TYPE_MYSTERY]  = sTypeBgGfx_Mystery,
    [TYPE_FIRE]     = sTypeBgGfx_Fire,
    [TYPE_WATER]    = sTypeBgGfx_Water,
    [TYPE_GRASS]    = sTypeBgGfx_Grass,
    [TYPE_ELECTRIC] = sTypeBgGfx_Electric,
    [TYPE_PSYCHIC]  = sTypeBgGfx_Psychic,
    [TYPE_ICE]      = sTypeBgGfx_Ice,
    [TYPE_DRAGON]   = sTypeBgGfx_Dragon,
    [TYPE_DARK]     = sTypeBgGfx_Dark,
    [TYPE_FAIRY]    = sTypeBgGfx_Fairy,
    [TYPE_STELLAR]  = sTypeBgGfx_Stellar,
};

static const u16 *const sTypeBgPal[NUMBER_OF_MON_TYPES] =
{
    [TYPE_NONE]     = sTypeBgPal_None,
    [TYPE_NORMAL]   = sTypeBgPal_Normal,
    [TYPE_FIGHTING] = sTypeBgPal_Fight,
    [TYPE_FLYING]   = sTypeBgPal_Flying,
    [TYPE_POISON]   = sTypeBgPal_Poison,
    [TYPE_GROUND]   = sTypeBgPal_Ground,
    [TYPE_ROCK]     = sTypeBgPal_Rock,
    [TYPE_BUG]      = sTypeBgPal_Bug,
    [TYPE_GHOST]    = sTypeBgPal_Ghost,
    [TYPE_STEEL]    = sTypeBgPal_Steel,
    [TYPE_MYSTERY]  = sTypeBgPal_Mystery,
    [TYPE_FIRE]     = sTypeBgPal_Fire,
    [TYPE_WATER]    = sTypeBgPal_Water,
    [TYPE_GRASS]    = sTypeBgPal_Grass,
    [TYPE_ELECTRIC] = sTypeBgPal_Electric,
    [TYPE_PSYCHIC]  = sTypeBgPal_Psychic,
    [TYPE_ICE]      = sTypeBgPal_Ice,
    [TYPE_DRAGON]   = sTypeBgPal_Dragon,
    [TYPE_DARK]     = sTypeBgPal_Dark,
    [TYPE_FAIRY]    = sTypeBgPal_Fairy,
    [TYPE_STELLAR]  = sTypeBgPal_Stellar,
};

#define TAG_STARTER_CURSOR 0x3100
#define TAG_STARTER_BALL   0x3101
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
#define tBallSprite    data[7]

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

// Cell centers for the 3x3 in menu.bin (icons + cursor).
static const u8 sGridCoords[STARTER_SLOTS_PER_REGION][2] =
{
    {36, 44}, {72, 44}, {108, 44},
    {36, 80}, {72, 80}, {108, 80},
    {36, 116}, {72, 116}, {108, 116},
};

// mGBA sprite Position is OAM top-left. pokeemerald sprite x/y is the center.
// Front 64x64 OAM (152, 28) → center (184, 60).
#define PIC_X 184
#define PIC_Y 60
// Type icons are 32x16. One: OAM (168, 116). Two: (150, 116) and (186, 116).
#define TYPE_ICON_Y 124
#define TYPE_ICON_X_SINGLE 184
#define TYPE_ICON_X0 166
#define TYPE_ICON_X1 202
// Header pokéball is 16x16. Sit in the left cap of the header bar.
#define POKEBALL_X 11
#define POKEBALL_Y 10
#define TYPE_BG_PALETTE 1
#define TYPE_BG_SCROLL  0x35 // 0.5px per frame, down-left
// Sprite x/y is the 64x64 center (OAM is x-32, y-32). Offset keeps the
// 38x38 cursor art on the cell (slot 0 OAM top-left stays at 17, 25).
#define CURSOR_OFFSET_X 13
#define CURSOR_OFFSET_Y 13

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
    {
        .bg = 3,
        .charBaseIndex = 1,
        .mapBaseIndex = 7,
        .screenSize = 0,
        .paletteMode = 0,
        .priority = 3,
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
        .tilemapTop = 17,
        .width = 28,
        .height = 3,
        .paletteNum = 15,
        .baseBlock = 55
    },
    { // name
        .bg = 0,
        .tilemapLeft = 19,
        .tilemapTop = 12,
        .width = 10,
        .height = 2,
        .paletteNum = 15,
        .baseBlock = 139
    },
    DUMMY_WIN_TEMPLATE,
};

static const struct CompressedSpriteSheet sCursorSpriteSheet =
{
    .data = sCursor_Gfx,
    .size = 0x800,
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
    .shape = SPRITE_SHAPE(64x64),
    .x = 0,
    .matrixNum = 0,
    .size = SPRITE_SIZE(64x64),
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

static const struct CompressedSpriteSheet sPokeballSpriteSheet =
{
    .data = sPokeball_Gfx,
    .size = 0x80,
    .tag = TAG_STARTER_BALL
};

static const struct SpritePalette sPokeballSpritePalette =
{
    .data = sPokeball_Pal,
    .tag = TAG_STARTER_BALL
};

static const struct OamData sOam_Pokeball =
{
    .y = 0,
    .affineMode = ST_OAM_AFFINE_OFF,
    .objMode = ST_OAM_OBJ_NORMAL,
    .mosaic = FALSE,
    .bpp = ST_OAM_4BPP,
    .shape = SPRITE_SHAPE(16x16),
    .x = 0,
    .matrixNum = 0,
    .size = SPRITE_SIZE(16x16),
    .tileNum = 0,
    .priority = 0,
    .paletteNum = 0,
    .affineParam = 0,
};

static const union AnimCmd sAnim_Pokeball[] =
{
    ANIMCMD_FRAME(0, 0),
    ANIMCMD_END,
};

static const union AnimCmd *const sAnims_Pokeball[] = { sAnim_Pokeball };

static const struct SpriteTemplate sSpriteTemplate_Pokeball =
{
    .tileTag = TAG_STARTER_BALL,
    .paletteTag = TAG_STARTER_BALL,
    .oam = &sOam_Pokeball,
    .anims = sAnims_Pokeball,
    .images = NULL,
    .affineAnims = gDummySpriteAffineAnimTable,
    .callback = SpriteCallbackDummy,
};

static EWRAM_DATA u16 sStarterChoices[STARTER_CHOICE_COUNT] = {0};
static EWRAM_DATA bool8 sStarterChoicesInitialized = FALSE;
static EWRAM_DATA u8 sIconSprites[STARTER_SLOTS_PER_REGION] = {0};
static EWRAM_DATA u16 sTypeBgTilemap[32 * 32] = {0};
static EWRAM_DATA u8 sLoadedTypeBg;
static EWRAM_DATA bool8 sTypeBgLoaded;

static void CB2_StarterChoose(void);
static void VblankCB_StarterChoose(void);
static void Task_HandleStarterInput(u8 taskId);
static void InitStarterChooseGfx(void);
static void CreateStarterChooseSprites(u8 taskId);
static void RefreshRegionIcons(u8 taskId);
static void RefreshSelection(u8 taskId);
static void InitTypeBgTilemap(void);
static void SetTypeBackground(enum Type type);
static void PrintHeader(u8 region);
static void PrintFooter(bool32 confirm);
static void PrintSpeciesName(enum Species species);
static void UpdateTypeIcons(u8 taskId, enum Species species);
static void DestroyIconSprites(void);
static void DestroyPicSprite(u8 taskId);
static void SpriteCB_WaitThenPlayFrontAnim(struct Sprite *sprite);
static void ExitStarterChoose(u8 taskId, u16 choice);
static u16 GetChoiceIndex(u8 region, u8 cursor);
static enum Species GetChoiceSpecies(u8 region, u8 cursor);
static s32 StepCursor(u8 region, s32 cursor, s32 delta);
static void SetCursorSpritePos(u8 spriteId, u8 cursor);

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
    ChangeBgX(3, 0, BG_COORD_SET);
    ChangeBgY(3, 0, BG_COORD_SET);

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
    ShowBg(3);

    if (!sStarterChoicesInitialized)
        InitStarterChoices();

    taskId = CreateTask(Task_HandleStarterInput, 0);
    gTasks[taskId].tRegion = 0;
    gTasks[taskId].tCursor = 0;
    gTasks[taskId].tConfirm = FALSE;
    gTasks[taskId].tPicSprite = SPRITE_NONE;
    gTasks[taskId].tType0 = SPRITE_NONE;
    gTasks[taskId].tType1 = SPRITE_NONE;
    gTasks[taskId].tBallSprite = SPRITE_NONE;
    CreateStarterChooseSprites(taskId);
    RefreshRegionIcons(taskId);
    RefreshSelection(taskId);
}

static void CB2_StarterChoose(void)
{
    ChangeBgX(3, TYPE_BG_SCROLL, BG_COORD_ADD);
    ChangeBgY(3, TYPE_BG_SCROLL, BG_COORD_SUB);
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
    SetBgTilemapBuffer(3, sTypeBgTilemap);
    InitTypeBgTilemap();
    sTypeBgLoaded = FALSE;
    LoadMonIconPalettes();
    LoadCompressedSpriteSheet(&sCursorSpriteSheet);
    LoadSpritePalette(&sCursorSpritePalette);
    LoadCompressedSpriteSheet(&sPokeballSpriteSheet);
    LoadSpritePalette(&sPokeballSpritePalette);
    LoadCompressedSpriteSheet(&gSpriteSheet_MoveTypes);
    LoadPalette(gMoveTypes_Pal, OBJ_PLTT_ID(13), 3 * PLTT_SIZE_4BPP);
}

static void CreateStarterChooseSprites(u8 taskId)
{
    u8 i;
    u8 spriteId;

    for (i = 0; i < STARTER_SLOTS_PER_REGION; i++)
        sIconSprites[i] = SPRITE_NONE;

    spriteId = CreateSprite(&sSpriteTemplate_Cursor, 0, 0, 0);
    gTasks[taskId].tCursorSprite = spriteId;
    SetCursorSpritePos(spriteId, 0);

    spriteId = CreateSprite(&sSpriteTemplate_Pokeball, POKEBALL_X, POKEBALL_Y, 0);
    gTasks[taskId].tBallSprite = spriteId;

    spriteId = CreateSprite(&gSpriteTemplate_MoveTypes, TYPE_ICON_X_SINGLE, TYPE_ICON_Y, 1);
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

static void SetCursorSpritePos(u8 spriteId, u8 cursor)
{
    gSprites[spriteId].x = sGridCoords[cursor][0] + CURSOR_OFFSET_X;
    gSprites[spriteId].y = sGridCoords[cursor][1] + CURSOR_OFFSET_Y;
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
        sIconSprites[i] = CreateMonIcon(species, SpriteCB_MonIcon, sGridCoords[i][0], sGridCoords[i][1], 2, 0);
        if (sIconSprites[i] < MAX_SPRITES)
        {
            gSprites[sIconSprites[i]].oam.priority = 1;
            SetPartyHPBarSprite(&gSprites[sIconSprites[i]], 0);
        }
        else
            sIconSprites[i] = SPRITE_NONE;
    }
}

static void InitTypeBgTilemap(void)
{
    u32 x, y;
    u16 tile;

    for (y = 0; y < 32; y++)
    {
        for (x = 0; x < 32; x++)
        {
            tile = (x % 4) + (y % 4) * 4;
            sTypeBgTilemap[y * 32 + x] = tile | (TYPE_BG_PALETTE << 12);
        }
    }
    CopyBgTilemapBufferToVram(3);
}

static void SetTypeBackground(enum Type type)
{
    if (type >= NUMBER_OF_MON_TYPES)
        type = TYPE_NORMAL;
    if (sTypeBgLoaded && type == sLoadedTypeBg)
        return;

    DecompressDataWithHeaderVram(sTypeBgGfx[type], (void *)BG_CHAR_ADDR(1));
    LoadPalette(sTypeBgPal[type], BG_PLTT_ID(TYPE_BG_PALETTE), PLTT_SIZE_4BPP);
    sLoadedTypeBg = type;
    sTypeBgLoaded = TRUE;
}

static void PrintHeader(u8 region)
{
    const u8 *label = sRegionLabels[region];
    s32 titleX = GetStringCenterAlignXOffset(FONT_NORMAL, sText_ChooseStarter, 120) - 15;
    s32 regionX = 120 + GetStringCenterAlignXOffset(FONT_NARROW, label, 96);

    FillWindowPixelBuffer(WIN_HEADER, PIXEL_FILL(0));
    AddTextPrinterParameterized3(WIN_HEADER, FONT_NORMAL, titleX, 3, sHeaderTextColors, 0, sText_ChooseStarter);
    AddTextPrinterParameterized3(WIN_HEADER, FONT_NARROW, regionX, 3, sHeaderTextColors, 0, label);
    PutWindowTilemap(WIN_HEADER);
    CopyWindowToVram(WIN_HEADER, COPYWIN_FULL);
}

static void PrintFooter(bool32 confirm)
{
    const u8 *text = confirm ? sText_FooterConfirm : sText_FooterBrowse;
    s32 x = GetStringCenterAlignXOffset(FONT_NORMAL, text, 224);

    FillWindowPixelBuffer(WIN_FOOTER, PIXEL_FILL(0));
    AddTextPrinterParameterized3(WIN_FOOTER, FONT_NORMAL, x, 7, sHeaderTextColors, 0, text);
    PutWindowTilemap(WIN_FOOTER);
    CopyWindowToVram(WIN_FOOTER, COPYWIN_FULL);
}

static void PrintSpeciesName(enum Species species)
{
    const u8 *name = GetSpeciesName(species);
    s32 x = GetStringCenterAlignXOffset(FONT_NORMAL, name, 80) - 8;

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
        gSprites[sprite0].x = TYPE_ICON_X_SINGLE;
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

    SetCursorSpritePos(cursorSprite, cursor);

    DestroyPicSprite(taskId);

    // 0 is female and loads anim_frontf.png. 0xFF keeps the base front sheet (anim_front.png).
    picSprite = CreateMonPicSprite(species, FALSE, 0xFF, TRUE, PIC_X, PIC_Y, 10, TAG_NONE);
    gSprites[picSprite].oam.priority = 1;
    gSprites[picSprite].data[0] = species;
    gSprites[picSprite].data[1] = TRUE; // sDontFlip: battle-style, no extra affine flip
    gSprites[picSprite].callback = SpriteCB_WaitThenPlayFrontAnim;
    gTasks[taskId].tPicSprite = picSprite;

    PrintHeader(region);
    PrintFooter(gTasks[taskId].tConfirm);
    PrintSpeciesName(species);
    UpdateTypeIcons(taskId, species);
    SetTypeBackground(GetSpeciesType(species, 0));
}

static void DestroyPicSprite(u8 taskId)
{
    u8 picSprite = gTasks[taskId].tPicSprite;

    if (picSprite == SPRITE_NONE)
        return;

    StopPokemonAnimationDelayTask();
    FreeSpriteOamMatrix(&gSprites[picSprite]);
    FreeAndDestroyMonPicSprite(picSprite);
    gTasks[taskId].tPicSprite = SPRITE_NONE;
}

static void SpriteCB_WaitThenPlayFrontAnim(struct Sprite *sprite)
{
    if (!gPaletteFade.active)
        PokemonSummaryDoMonAnimation(sprite, sprite->data[0], FALSE);
}

static void ExitStarterChoose(u8 taskId, u16 choice)
{
    DestroyIconSprites();
    DestroyPicSprite(taskId);
    if (gTasks[taskId].tCursorSprite != SPRITE_NONE)
        DestroySprite(&gSprites[gTasks[taskId].tCursorSprite]);
    if (gTasks[taskId].tType0 != SPRITE_NONE)
        DestroySprite(&gSprites[gTasks[taskId].tType0]);
    if (gTasks[taskId].tType1 != SPRITE_NONE)
        DestroySprite(&gSprites[gTasks[taskId].tType1]);
    if (gTasks[taskId].tBallSprite != SPRITE_NONE)
        DestroySpriteAndFreeResources(&gSprites[gTasks[taskId].tBallSprite]);
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
