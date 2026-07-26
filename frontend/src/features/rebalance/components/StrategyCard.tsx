import { useMemo, useState } from "react";
import { Alert, Box, Button, Card, CardContent, Grid, IconButton, Typography } from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutlined";

import { mapPortfolioToAssets } from "../mappers/portfolio.mapper";

import type { UserStrategy } from "../types/user";
import type { SortConfig } from "../types/sort";
import type { Action, Asset } from "../types/rebalance";
import type { RebalanceExecutionResult } from "../types/strategy";

import { buildRebalanceActions } from "../utils/buildActions";
import { sortAssets } from "../utils/sortAssets";

import { executeRebalance, deleteStrategy } from "../api/client";
import { buttonStyles } from "../../../shared/theme/buttons";

import PortfolioTable from "./PortfolioTable";
import PortfolioPieChart from "./PortfolioPieChart";
import PortfolioBarChart from "./PortfolioBarChart";
import RebalanceDialog from "./RebalanceDialog";


export default function StrategyCard({
  strategy,
  onUpdated,
}: {
  strategy: UserStrategy;

  onUpdated: () => Promise<void>;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [open, setOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [sortConfig] =
    useState<SortConfig>({
        field: "portfolioWeight",
        direction: "desc",
    });
  const assets: Asset[] = useMemo(() => {
    const mapped =
      mapPortfolioToAssets(
      strategy.portfolio
      );

    return sortAssets(
      mapped,
      sortConfig
    );
  }, [
    strategy.portfolio,
    sortConfig,
  ]);
  const actions: Action[] = buildRebalanceActions(assets);

  const handleExecute = async (): Promise<RebalanceExecutionResult> => {
    const result = await executeRebalance(strategy.id);

    await onUpdated();

    return result;
  };

  const handleDelete = async () => {
    if (
      !window.confirm(
        `Удалить стратегию «${strategy.indexInfo.name}» по счёту «${strategy.brokerInfo.account.name}»?`
      )
    ) {
      return;
    }

    try {
      setDeleting(true);

      await deleteStrategy(strategy.id);
      await onUpdated();
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        {/* HEADER */}
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            mb: 2,
          }}
        >
          {/* LEFT */}
          <Box>
            <Typography
              variant="h6"
              sx={{ fontWeight: "bold" }}
            >
              {strategy.brokerInfo.name}
            </Typography>

            <Typography color="text.secondary">
              Индекс: {strategy.indexInfo.name}
            </Typography>

            <Typography color="text.secondary">
              Счёт:{" "}
              {
                strategy.brokerInfo.account.name || "Без названия"
              }
            </Typography>

            <Typography color="text.secondary">
              Свободные средства:{" "}
              {strategy.freeCash.toLocaleString()} ₽
            </Typography>

            <Typography color="text.secondary">
              После балансировки:{" "}
              {strategy.freeCashAfter.toLocaleString()} ₽
            </Typography>
          </Box>

          {/* RIGHT */}
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
            }}
          >
            <Button
              sx={buttonStyles}
              disabled={
                strategy.accountDeleted ||
                actions.length === 0 ||
                deleting
              }
              onClick={() => setOpen(true)}
            >
              Балансировка
            </Button>

            <IconButton
              onClick={handleDelete}
              disabled={deleting}
              title="Удалить стратегию"
            >
              <DeleteOutlineIcon />
            </IconButton>

            <IconButton
              onClick={() =>
                setCollapsed(!collapsed)
              }
            >
              <ExpandMoreIcon
                style={{
                  transform: collapsed
                    ? "rotate(180deg)"
                    : "rotate(0deg)",

                  transition: "0.2s",
                }}
              />
            </IconButton>
          </Box>
        </Box>

        {strategy.accountDeleted && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Счёт помечен удалённым у брокера — балансировка недоступна.
            Обновите список счетов или удалите стратегию.
          </Alert>
        )}

        {/* CONTENT */}
        {!collapsed && (
          <>
            {/* CHARTS */}
            <Grid container spacing={3}>
              {/* PIE */}
              <Grid size={{ xs: 12, md: 3 }}>
                <Typography sx={{ mb: 1 }}>
                  Структура портфеля
                </Typography>

                <PortfolioPieChart
                  data={assets}
                />
              </Grid>

              {/* BAR */}
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography sx={{ mb: 1 }}>
                  Сравнение с индексом
                </Typography>

                <PortfolioBarChart
                  data={assets}
                />
              </Grid>
            </Grid>

            {/* TABLE */}
            <Box sx={{ mt: 3 }}>
              <PortfolioTable data={assets} />
            </Box>
          </>
        )}
      </CardContent>

      <RebalanceDialog
        open={open}
        onClose={() => setOpen(false)}
        actions={actions}
        onExecute={handleExecute}
      />
    </Card>
  );
}
