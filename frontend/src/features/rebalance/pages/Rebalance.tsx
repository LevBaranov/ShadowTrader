import { useState } from "react";
import {
  Box,
  Typography,
  Button,
  CircularProgress,
} from "@mui/material";


import { buttonStyles } from "../../../shared/theme/buttons";

import StrategyDialog from "../components/StrategyDialog";
import type { 
  UserStrategy
} from "../types/user";
import { useCurrentUser } from "../hooks/useCurrentUser";
import StrategyCard from "../components/StrategyCard";


export default function Rebalance() {
  const { user, loading, refresh, } = useCurrentUser();
  const [strategyDialog, setStrategyDialog] = useState(false);
  
  if (loading) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          mt: 10,
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if ( !user || !user.strategies || user.strategies.length === 0 ) {
    return (
      <Box
        sx={{
          textAlign: "center",
          mt: 10,
        }}
      >
        <Typography
          variant="h5"
          sx={{ mb: 2 }}
        >
          У вас пока нет стратегий
        </Typography>

        <Button
          variant="contained"
          sx={buttonStyles}
          onClick={() =>
            setStrategyDialog(true)
          }
        >
          Добавить стратегию
        </Button>

        <StrategyDialog
          open={strategyDialog}
          onClose={() =>
            setStrategyDialog(false)
          }
          onSave={async () => {
            setStrategyDialog(false);

            await refresh();
          }}
        />
      </Box>
    );
  }

  return (
    <Box>
      <Typography
        variant="h5"
        sx={{
          mb: 3,
          fontWeight: "bold",
        }}
      >
        Портфели
      </Typography>

      {user.strategies.map(
        (
          strategy: UserStrategy
        ) => (
          <StrategyCard
            key={strategy.brokerInfo.id}
            strategy={strategy}
            onUpdated={refresh}
          />
        )
      )}
    </Box>
  );
}