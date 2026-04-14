FUNCTION_BLOCK FB_RecipeManager_Tc
VAR_INPUT
    SelectedRecipeId : E_RecipeId_Tc;
    CustomRecipe : ST_ExtruderRecipe;
END_VAR
VAR_OUTPUT
    ActiveRecipeId : E_RecipeId_Tc := E_RecipeId_Tc.DEFAULT;
    ActiveRecipe : ST_ExtruderRecipe;
END_VAR

CASE SelectedRecipeId OF
    E_RecipeId_Tc.HDPE_PIPE:
        ActiveRecipeId := E_RecipeId_Tc.HDPE_PIPE;
        ActiveRecipe := GVL_ExtruderRecipes.gcRecipeHdpePipe;

    E_RecipeId_Tc.PVC_PROFILE:
        ActiveRecipeId := E_RecipeId_Tc.PVC_PROFILE;
        ActiveRecipe := GVL_ExtruderRecipes.gcRecipePvcProfile;

    E_RecipeId_Tc.CUSTOM:
        ActiveRecipeId := E_RecipeId_Tc.CUSTOM;
        ActiveRecipe := CustomRecipe;

ELSE
    ActiveRecipeId := E_RecipeId_Tc.DEFAULT;
    ActiveRecipe := GVL_ExtruderRecipes.gcRecipeDefault;
END_CASE;

END_FUNCTION_BLOCK
