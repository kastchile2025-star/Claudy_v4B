import { Command } from 'commander';
import chalk from 'chalk';
import ora from 'ora';
import { loadConfig, saveConfig } from '../config.js';
import { OpenCodeClient } from '../opencode.js';

export const modelsCommand = new Command('models')
  .description('Gestionar modelos LLM');

modelsCommand
  .command('list')
  .alias('ls')
  .description('Listar modelos disponibles en OpenCode')
  .option('-s, --search <query>', 'Filtrar por texto')
  .option('-l, --limit <n>', 'Limitar resultados', '50')
  .action(async (options) => {
    const config = loadConfig();
    const spinner = ora('Obteniendo modelos desde OpenCode...').start();

    try {
      const client = new OpenCodeClient(config.opencode);
      let models = await client.listModels();

      if (options.search) {
        const query = options.search.toLowerCase();
        models = models.filter(
          (m) =>
            m.id.toLowerCase().includes(query) ||
            m.name.toLowerCase().includes(query)
        );
      }

      const limit = parseInt(options.limit);
      const limited = models.slice(0, limit);

      spinner.succeed(chalk.green(`${models.length} modelos encontrados`));

      if (models.length === 0) {
        console.log(chalk.yellow('\nNo hay modelos. Asegúrate de:'));
        console.log(chalk.gray('  1. Tener OpenCode corriendo'));
        console.log(chalk.gray('  2. Haber configurado al menos un provider'));
        return;
      }

      console.log('');
      limited.forEach((model) => {
        const isDefault = model.id === config.opencode.defaultModel;
        const marker = isDefault ? chalk.green(' ★') : '';
        console.log(chalk.yellow(`▸ ${model.id}${marker}`));
        console.log(chalk.gray(`  ${model.name}`));
        if (model.description) {
          const desc = model.description.substring(0, 100);
          console.log(chalk.gray(`  ${desc}${model.description.length > 100 ? '...' : ''}`));
        }
        if (model.context_length) {
          console.log(chalk.gray(`  Context: ${model.context_length.toLocaleString()} tokens`));
        }
        console.log('');
      });

      if (models.length > limit) {
        console.log(chalk.gray(`... y ${models.length - limit} más. Usa --limit.\n`));
      }
    } catch (error: any) {
      spinner.fail(chalk.red('Error: ' + error.message));
      process.exit(1);
    }
  });

modelsCommand
  .command('current')
  .description('Mostrar modelo actual')
  .action(() => {
    const config = loadConfig();
    console.log(chalk.cyan('Modelo actual: ') + chalk.yellow(config.opencode.defaultModel));
    console.log(chalk.cyan('OpenCode URL:  ') + chalk.yellow(config.opencode.baseUrl));
  });

modelsCommand
  .command('set <model>')
  .description('Establecer modelo predeterminado')
  .action((model: string) => {
    const config = loadConfig();

    if (!model.includes('/')) {
      console.log(chalk.red('✗ Formato inválido. Usa: provider/model'));
      process.exit(1);
    }

    config.opencode.defaultModel = model;
    saveConfig(config);
    console.log(chalk.green(`✓ Modelo predeterminado: ${model}`));
  });
