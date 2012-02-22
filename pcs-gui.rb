require 'sinatra'

@nodes = (1..7)
  
get '/' do
  @nodes = (1..7)
  @cur_node = 1
  erb :index
end

get '/nodes/?' do
  @nodes = (1..7)
  @cur_node = 1
  erb :index
end

get '/nodes/:node' do
  @nodes = (1..7)
  @cur_node = params[:node].to_i
  @cur_node = 1 if @cur_node == 0
  erb :index
end

get '*' do
  @cur_node = 1
  @nodes = [1,2]
  erb :index
end
