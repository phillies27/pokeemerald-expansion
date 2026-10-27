#ifndef GUARD_STARTER_CHOOSE_H
#define GUARD_STARTER_CHOOSE_H

#define STARTER_REGION_COUNT     10
#define STARTER_SLOTS_PER_REGION 9
#define STARTER_CHOICE_COUNT     (STARTER_REGION_COUNT * STARTER_SLOTS_PER_REGION)

extern const u16 gBirchBagGrass_Pal[];
extern const u32 gBirchBagTilemap[];
extern const u32 gBirchGrassTilemap[];
extern const u32 gBirchBagGrass_Gfx[];
extern const u32 gPokeballSelection_Gfx[];

u16 GetStarterPokemon(u16 chosenStarterId);
void CB2_ChooseStarter(void);
void InitStarterChoices(void);
u16 *GetStarterChoiceList(void);
void BufferStarterTypeExample(void);

#endif // GUARD_STARTER_CHOOSE_H
