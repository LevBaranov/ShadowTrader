import { useEffect, useState } from "react";
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  IconButton,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";

import { buttonStyles } from "../theme/buttons";
import { getPortfolio } from "../services/api";

import PortfolioTable from "../components/PortfolioTable";
import PortfolioBarChart from "../components/PortfolioBarChart";
import PortfolioPieChart from "../components/PortfolioPieChart";
import RebalanceDialog from "../components/RebalanceDialog";
import StrategyDialog from "../components/StrategyDialog";

type Asset = {
  id: number;
  ticker: string;
  name: string;
  indexWeight: number;
  portfolioWeight: number;
  quantity: number;
  diff: number;
};
type Action = {
  type: "BUY" | "SELL";
  ticker: string;
  quantity: number;
};

export default function Rebalance() {
  const [data, setData] = useState<Asset[]>([]);
  const [open, setOpen] = useState(false);
  
  const [strategy, setStrategy] = useState<any | null>(null);
  const [strategyDialog, setStrategyDialog] = useState(false);

  const [collapsed, setCollapsed] = useState(false);
  
  useEffect(() => {
    if (strategy) {
      getPortfolio().then(setData); // TODO: заменить на API
    }
  }, [strategy]);


  const buildActions = (data: Asset[]): Action[] => {
  return data
    .filter((row) => row.diff !== 0)
    .map((row) => ({
      type: row.diff > 0 ? "BUY" : "SELL",
      ticker: row.ticker,
      quantity: Math.abs(row.diff), 
    }));
};

  const actions = buildActions(data);

  if (!strategy) {
    return (
      <Box sx={{ textAlign: "center",  mt:10 }}>
        <Typography variant="h5" sx={{ mb:2 }}>
          У вас пока нет стратегии
        </Typography>

        <Button
          variant="contained"
          sx={buttonStyles}
          onClick={() => setStrategyDialog(true)}
        >
          Добавить стратегию
        </Button>

        <StrategyDialog
          open={strategyDialog}
          onClose={() => setStrategyDialog(false)}
          onSave={(s) => setStrategy(s)}
        />
      </Box>
    );
  }

  return (
    <Box>
      {/* КАРТОЧКА ПОРТФЕЛЯ */}
      <Card >
        <CardContent>
          {/* HEADER карточки */}
          <Box sx={{ display:"flex", justifyContent:"space-between", alignItems:"center" }}>
            {/* Название */}
            <Box>
              <Typography variant="h6" sx={{ fontWeight:"bold"}}>
                {strategy.portfolio}
              </Typography>
              <Typography color="text.secondary">
                Индекс: {strategy.index}
              </Typography>
            </Box>

            {/* Кнопки */}
            <Box sx={{ display:"flex", alignItems:"center" }}>
              <Button
                sx={buttonStyles}
                onClick={() => setOpen(true)}
                disabled={actions.length === 0}
              >
                Выполнить балансировку
              </Button>

              <IconButton onClick={() => setCollapsed(!collapsed)}>
                <ExpandMoreIcon
                  style={{
                    transform: collapsed ? "rotate(180deg)" : "rotate(0deg)",
                  }}
                />
              </IconButton>
            </Box>
          </Box>

          {/* Содержимое (сворачиваемое) */}

          {!collapsed && (
            <>
              {/* ГРАФИКИ */}
              <Grid container spacing={3}>
                {/* PIE */}
                <Grid sx={{ xs: 12, md: 6 }}>
                  <Typography sx={{ mb: 1 }}>Структура портфеля</Typography>
                  <PortfolioPieChart data={data} />

                </Grid>

                {/* BAR */}
                <Grid sx={{ xs: 12, md: 6 }}>
                  <Typography sx={{ mb: 1 }}> Сравнение с индексом</Typography>
                  <PortfolioBarChart  data={data} />

                </Grid>
              </Grid>

              {/* ТАБЛИЦА */}
              <PortfolioTable data={data} />
            </>
          )}
    
        </CardContent>
      </Card>
      <RebalanceDialog
        open={open}
        onClose={() => setOpen(false)}
        actions={actions}
      />
    </Box>
  
  );
}